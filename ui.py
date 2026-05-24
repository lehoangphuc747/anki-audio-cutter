# -*- coding: utf-8 -*-
"""
Main User Interface module for Audio Card Cutter.
"""
import os
import re
import sys
import threading
import traceback
from typing import Optional

from aqt import mw
from aqt.qt import (
    QAction, QColor, QComboBox, QDialog, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog,
    QKeySequence, QLabel, QLineEdit,
    QListWidget, QMenu, QMessageBox, QPainter, QPlainTextEdit, QPushButton,
    QScrollArea, QShortcut, QSlider, QStyle, QStyleOptionSlider, Qt,
    QTabWidget, QTableWidget, QTableWidgetItem, QTimer,
    QUrl, QVBoxLayout, QWidget, qconnect, QAbstractSlider, QSizePolicy
)
from aqt.utils import showWarning, tooltip

from ._tr import tr
from .player import HAS_MEDIA, QT_MAJOR
if HAS_MEDIA:
    from .player import QMediaPlayer, QAudioOutput, QMediaContent
else:
    QMediaPlayer = None
    QAudioOutput = None
    QMediaContent = None

from .constants import (
    PREVIEW_DURATION_SEC, REACTION_OFFSET_SEC, SEEK_STEP_LARGE_SEC, SEEK_STEP_SMALL_SEC,
    NUDGE_STEP_LARGE_SEC, NUDGE_STEP_SMALL_SEC, TICK_INTERVAL_MS, AUDIO_EXTENSIONS,
    STYLING_LBL_FILE_LOADED, STYLING_LBL_FILE_UNLOADED, STYLING_FFMPEG_STATUS,
    STYLING_PLAY_BUTTON, STYLING_NUDGE_BUTTON, STYLING_LBL_TIME, STYLING_QUEUE_LIST,
    STYLING_QUEUE_CUT_ALL, STYLING_DECK_BUTTON, STYLING_NOTETYPE_BUTTON,
    STYLING_ACTIVE_FIELD, STYLING_ACTIVE_LABEL, STYLING_LINE_EDIT_FOCUS,
    STYLING_SEARCH_DIALOG, STYLING_BTN_CUT, STYLING_BTN_ADD_NOTE, STYLING_BTN_CUT_AND_ADD,
    WAVEFORM_BAR_WIDTH, WAVEFORM_BAR_SPACING, STYLING_COMBO_SPEED_STYLING,
    STYLING_DIALOG_CRUD_BTN, STYLING_DIALOG_CRUD_DELETE, STYLING_SETTINGS_TAB,
    STYLING_SETTINGS_TABLE, STYLING_QUEUE_PLAY_BTN, STYLING_SETTINGS_BTN
)
from .ffmpeg_utils import (
    _probe_duration, _cut_audio_to_media, _is_ffmpeg_available, install_ffmpeg_windows,
    _ffmpeg_binary, FFmpegNotFoundError, extract_waveform,
    get_ffmpeg_version, check_ffmpeg_latest_version, update_ffmpeg_windows
)
from .anki_interop import (
    _config, _save_config, _add_note, _undo_last_note
)
from .widgets.waveform import AudioWaveformWidget
from .dialogs.deck_select import DeckSelectDialog
from .dialogs.notetype_select import NoteTypeSelectDialog
from .dialogs.settings import SettingsDialog



# =============================================================================
# Helpers
# =============================================================================

def fmt_time(sec: float) -> str:
    if not sec or sec < 0:
        sec = 0.0
    m = int(sec // 60)
    s = sec - m * 60
    return f"{m}:{s:05.2f}"


_TIME_RE = re.compile(r"^\s*(?:(\d+):)?(\d+(?:\.\d+)?)\s*$")
_TIME_RE_HMS = re.compile(r"^\s*(\d+):(\d+):(\d+(?:\.\d+)?)\s*$")


def parse_time(text: str) -> Optional[float]:
    """Parse 'ss', 'mm:ss[.ms]', or 'hh:mm:ss[.ms]' to seconds."""
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    m = _TIME_RE_HMS.match(text)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    m = _TIME_RE.match(text)
    if m:
        mm = int(m.group(1)) if m.group(1) else 0
        ss = float(m.group(2))
        return mm * 60 + ss
    return None


# =============================================================================
# Custom slider with region highlight
# =============================================================================

class AudioCutterDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent or mw)
        self.setWindowTitle(tr("window_title"))
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(900, 580)

        self._src_path: str = ""
        self._loaded_player_path: str = ""
        self._duration: float = 0.0
        self._field_editors: dict[str, QPlainTextEdit] = {}
        self._stop_at_ms: int = -1
        self._is_seeking_via_user: bool = False
        # Pending cut (Cut and Add are separate)
        self._pending_cut_file: str = ""
        # Undo: last created note + audio file
        self._last_note_id: Optional[int] = None
        self._last_audio_file: str = ""
        # Duplicate detection: list of (start, end) cut in this session per file
        self._cut_history: list[tuple[float, float]] = []
        self._cut_history_file: str = ""
        # Batch queue: list of [start, end, filename]
        self._batch_queue: list[list] = []
        self._last_batch_files: list[str] = []
        # Deck/notetype selection
        self._deck_names: list[str] = []
        self._notetype_names: list[str] = []
        self._selected_deck: str = ""
        self._selected_notetype: str = ""

        self._build_ui()
        self._setup_player()
        self._setup_shortcuts()
        self._populate_decks_notetypes()
        self._render_fields_for_current_notetype()
        self.input_tags.setText(_config().get("last_tags") or "")
        self._set_audio_loaded(False)
        self._refresh_ffmpeg_status()

    # ------------------------- ffmpeg banner --------------

    def _refresh_ffmpeg_status(self) -> None:
        if _is_ffmpeg_available():
            self.lbl_ffmpeg_status.setVisible(False)
            self.btn_install_ffmpeg.setVisible(False)
        else:
            self.lbl_ffmpeg_status.setText(tr("ffmpeg_banner"))
            self.lbl_ffmpeg_status.setVisible(True)
            self.btn_install_ffmpeg.setVisible(sys.platform.startswith("win"))

    def _on_install_ffmpeg(self) -> None:
        if install_ffmpeg_windows(self):
            self._refresh_ffmpeg_status()

    # ------------------------- UI -------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)

        # 1. File picker -----------------------------------
        file_row = QHBoxLayout()
        self.btn_pick = QPushButton(tr("btn_select_file"))
        self.lbl_file = QLabel(tr("no_file_selected"))
        self.lbl_file.setStyleSheet(STYLING_LBL_FILE_UNLOADED)
        self.lbl_file.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.btn_install_ffmpeg = QPushButton(tr("btn_install_ffmpeg"))
        self.btn_install_ffmpeg.setToolTip(tr("tooltip_install_ffmpeg"))
        self.btn_settings = QPushButton(tr("settings_btn_settings"))
        self.btn_settings.setToolTip(tr("settings_tooltip"))
        self.btn_settings.setStyleSheet(STYLING_SETTINGS_BTN)
        file_row.addWidget(self.btn_pick)
        file_row.addWidget(self.lbl_file, 1)
        file_row.addWidget(self.btn_install_ffmpeg)
        file_row.addWidget(self.btn_settings)
        outer.addLayout(file_row)

        # FFmpeg status banner
        self.lbl_ffmpeg_status = QLabel()
        self.lbl_ffmpeg_status.setStyleSheet(STYLING_FFMPEG_STATUS)
        self.lbl_ffmpeg_status.setVisible(False)
        outer.addWidget(self.lbl_ffmpeg_status)

        # 2. Player + slider --------------------------------
        play_row = QHBoxLayout()
        self.btn_play = QPushButton(tr("btn_play"))
        self.btn_play.setMinimumWidth(64)
        self.btn_play.setStyleSheet(STYLING_PLAY_BUTTON)
        self.lbl_time = QLabel("0:00.00 / 0:00.00")
        self.lbl_time.setStyleSheet(STYLING_LBL_TIME)
        self.lbl_time.setMinimumWidth(150)
        self.slider_pos = AudioWaveformWidget(self)
        self.slider_pos.setRange(0, 0)
        self.slider_pos.setSingleStep(100)
        self.slider_pos.setPageStep(2000)
        self.slider_pos.set_region_callback(self._on_waveform_region_changed)

        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["0.7x", "0.8x", "0.9x", "1.0x", "1.1x", "1.2x", "1.5x"])
        self.combo_speed.setCurrentText("1.0x")
        self.combo_speed.setFixedWidth(55)
        self.combo_speed.setStyleSheet(STYLING_COMBO_SPEED_STYLING)

        play_row.addWidget(self.btn_play)
        play_row.addWidget(self.slider_pos, 1)
        play_row.addWidget(self.lbl_time)
        play_row.addWidget(self.combo_speed)
        outer.addLayout(play_row)

        # 3. Region selectors -------------------------------
        region_box = QGroupBox(tr("region_group"))
        rl = QGridLayout(region_box)

        # Start Row
        rl.addWidget(QLabel(tr("label_start")), 0, 0)
        self.input_start = QLineEdit("0:00.00")
        self.input_start.setFixedWidth(80)
        self.input_start.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_start.setStyleSheet(STYLING_LINE_EDIT_FOCUS)
        rl.addWidget(self.input_start, 0, 1)

        self.btn_set_start = QPushButton(tr("btn_set_start"))
        self.btn_set_start.setToolTip(tr("tooltip_set_start"))
        self.btn_set_start.setMinimumWidth(90)
        rl.addWidget(self.btn_set_start, 0, 2)

        # Nudge Start Buttons
        nudge_s_layout = QHBoxLayout()
        nudge_s_layout.setContentsMargins(0, 0, 0, 0)
        nudge_s_layout.setSpacing(2)

        self.btn_nudge_s_m500 = QPushButton("-0.5s")
        self.btn_nudge_s_m500.setStyleSheet(STYLING_NUDGE_BUTTON)
        self.btn_nudge_s_m100 = QPushButton("-0.1s")
        self.btn_nudge_s_m100.setStyleSheet(STYLING_NUDGE_BUTTON)
        self.btn_nudge_s_p100 = QPushButton("+0.1s")
        self.btn_nudge_s_p100.setStyleSheet(STYLING_NUDGE_BUTTON)
        self.btn_nudge_s_p500 = QPushButton("+0.5s")
        self.btn_nudge_s_p500.setStyleSheet(STYLING_NUDGE_BUTTON)
        nudge_s_layout.addWidget(self.btn_nudge_s_m500)
        nudge_s_layout.addWidget(self.btn_nudge_s_m100)
        nudge_s_layout.addWidget(self.btn_nudge_s_p100)
        nudge_s_layout.addWidget(self.btn_nudge_s_p500)
        rl.addLayout(nudge_s_layout, 0, 3)

        self.btn_play_start = QPushButton(tr("btn_hear_start"))
        self.btn_play_start.setMinimumWidth(90)
        rl.addWidget(self.btn_play_start, 0, 4)

        # End Row
        rl.addWidget(QLabel(tr("label_end")), 1, 0)
        self.input_end = QLineEdit("0:00.00")
        self.input_end.setFixedWidth(80)
        self.input_end.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_end.setStyleSheet(STYLING_LINE_EDIT_FOCUS)
        rl.addWidget(self.input_end, 1, 1)

        self.btn_set_end = QPushButton(tr("btn_set_end"))
        self.btn_set_end.setToolTip(tr("tooltip_set_end"))
        self.btn_set_end.setMinimumWidth(90)
        rl.addWidget(self.btn_set_end, 1, 2)

        # Nudge End Buttons
        nudge_e_layout = QHBoxLayout()
        nudge_e_layout.setContentsMargins(0, 0, 0, 0)
        nudge_e_layout.setSpacing(2)
        self.btn_nudge_e_m500 = QPushButton("-0.5s")
        self.btn_nudge_e_m500.setStyleSheet(STYLING_NUDGE_BUTTON)
        self.btn_nudge_e_m100 = QPushButton("-0.1s")
        self.btn_nudge_e_m100.setStyleSheet(STYLING_NUDGE_BUTTON)
        self.btn_nudge_e_p100 = QPushButton("+0.1s")
        self.btn_nudge_e_p100.setStyleSheet(STYLING_NUDGE_BUTTON)
        self.btn_nudge_e_p500 = QPushButton("+0.5s")
        self.btn_nudge_e_p500.setStyleSheet(STYLING_NUDGE_BUTTON)
        nudge_e_layout.addWidget(self.btn_nudge_e_m500)
        nudge_e_layout.addWidget(self.btn_nudge_e_m100)
        nudge_e_layout.addWidget(self.btn_nudge_e_p100)
        nudge_e_layout.addWidget(self.btn_nudge_e_p500)
        rl.addLayout(nudge_e_layout, 1, 3)

        self.btn_play_end = QPushButton(tr("btn_hear_end"))
        self.btn_play_end.setMinimumWidth(90)
        rl.addWidget(self.btn_play_end, 1, 4)

        # Actions Row
        actions_lay = QHBoxLayout()
        actions_lay.setContentsMargins(0, 4, 0, 0)
        self.btn_preview = QPushButton(tr("btn_preview"))
        self.btn_preview.setToolTip(tr("tooltip_preview"))
        self.btn_preview.setMinimumWidth(80)

        self.btn_cut = QPushButton(tr("btn_cut"))
        self.btn_cut.setToolTip(tr("tooltip_cut"))
        self.btn_cut.setStyleSheet(STYLING_BTN_CUT)
        self.btn_cut.setMinimumWidth(100)

        self.btn_play_cut = QPushButton(tr("btn_play_cut"))
        self.btn_play_cut.setToolTip(tr("tooltip_play_cut"))
        self.btn_play_cut.setEnabled(False)
        self.btn_play_cut.setMinimumWidth(80)

        self.btn_add_queue = QPushButton(tr("btn_add_queue"))
        self.btn_add_queue.setToolTip(tr("tooltip_add_queue"))
        self.btn_add_queue.setMinimumWidth(110)

        actions_lay.addStretch(1)
        actions_lay.addWidget(self.btn_preview)
        actions_lay.addWidget(self.btn_cut)
        actions_lay.addWidget(self.btn_play_cut)
        actions_lay.addWidget(self.btn_add_queue)
        rl.addLayout(actions_lay, 2, 0, 1, 5)

        # 3b. Batch queue -----------------------------------
        self.queue_box = QGroupBox(tr("queue_title", count=0))
        queue_layout = QHBoxLayout(self.queue_box)
        self.queue_list = QListWidget()
        self.queue_list.setMaximumHeight(90)
        self.queue_list.setStyleSheet(STYLING_QUEUE_LIST)
        queue_layout.addWidget(self.queue_list, 1)
        queue_btns = QVBoxLayout()
        self.btn_queue_play = QPushButton(tr("btn_queue_play"))
        self.btn_queue_play.setToolTip(tr("tooltip_queue_play"))
        self.btn_queue_play.setStyleSheet(STYLING_QUEUE_PLAY_BTN)
        self.btn_queue_remove = QPushButton(tr("btn_queue_remove"))
        self.btn_queue_remove.setToolTip(tr("tooltip_queue_remove"))
        self.btn_queue_clear = QPushButton(tr("btn_queue_clear"))
        self.btn_queue_cut_all = QPushButton(tr("btn_queue_cut_all"))
        self.btn_queue_cut_all.setStyleSheet(STYLING_QUEUE_CUT_ALL)
        queue_btns.addWidget(self.btn_queue_play)
        queue_btns.addWidget(self.btn_queue_remove)
        queue_btns.addWidget(self.btn_queue_clear)
        queue_btns.addWidget(self.btn_queue_cut_all)
        queue_btns.addStretch()
        queue_layout.addLayout(queue_btns)
        self.queue_box.setVisible(False)

        # 4. Note metadata ---------------------------------
        meta_box = QGroupBox(tr("note_group"))
        meta_outer = QVBoxLayout(meta_box)
        top_form = QFormLayout()
        top_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.btn_deck = QPushButton()
        self.btn_deck.setStyleSheet(STYLING_DECK_BUTTON)
        self.btn_notetype = QPushButton()
        self.btn_notetype.setStyleSheet(STYLING_NOTETYPE_BUTTON)
        self.combo_audio_field = QComboBox()
        top_form.addRow(tr("label_deck"), self.btn_deck)
        top_form.addRow(tr("label_notetype"), self.btn_notetype)
        top_form.addRow(tr("label_audio_field"), self.combo_audio_field)
        meta_outer.addLayout(top_form)

        # Scrollable fields area
        self.fields_container = QWidget()
        self.fields_layout = QFormLayout(self.fields_container)
        self.fields_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.fields_container)
        scroll.setMinimumHeight(160)
        meta_outer.addWidget(scroll, 1)

        tags_form = QFormLayout()
        tags_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.input_tags = QLineEdit()
        self.input_tags.setPlaceholderText(tr("tags_placeholder"))
        self.input_tags.setStyleSheet(STYLING_LINE_EDIT_FOCUS)
        tags_form.addRow(tr("label_tags"), self.input_tags)
        meta_outer.addLayout(tags_form)

        # 5. Action row ------------------------------------
        action_row = QHBoxLayout()
        action_row.addStretch(1)

        self.btn_undo = QPushButton(tr("btn_undo"))
        self.btn_undo.setToolTip(tr("tooltip_undo"))
        self.btn_undo.setEnabled(False)
        action_row.addWidget(self.btn_undo)

        self.btn_add_note = QPushButton(tr("btn_add_note"))
        self.btn_add_note.setEnabled(False)
        self.btn_add_note.setStyleSheet(STYLING_BTN_ADD_NOTE)
        action_row.addWidget(self.btn_add_note)

        self.btn_cut_and_add = QPushButton(tr("btn_cut_and_add"))
        self.btn_cut_and_add.setToolTip(tr("tooltip_cut_and_add"))
        self.btn_cut_and_add.setMinimumWidth(120)
        self.btn_cut_and_add.setStyleSheet(STYLING_BTN_CUT_AND_ADD)
        action_row.addWidget(self.btn_cut_and_add)
        
        # Horizontal Split layout for bottom components (Landscape optimized)
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(12)

        # Left Column: Cut Region + Cut Queue
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(region_box)
        left_layout.addWidget(self.queue_box)
        left_layout.addStretch(1)

        # Right Column: New Note metadata + Action buttons
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(meta_box, 1)
        right_layout.addLayout(action_row)

        columns_layout.addWidget(left_col, 2)
        columns_layout.addWidget(right_col, 3)

        outer.addLayout(columns_layout)

        # Centered, full-width shortcut hint at the very bottom
        hint_layout = QHBoxLayout()
        hint_layout.setContentsMargins(0, 4, 0, 0)
        hint = QLabel(tr("shortcut_hint"))
        hint.setStyleSheet(STYLING_LBL_FILE_UNLOADED + " font-size: 11px;")
        align_center = Qt.AlignmentFlag.AlignCenter if QT_MAJOR == 6 else Qt.AlignCenter
        hint.setAlignment(align_center)
        hint_layout.addWidget(hint)
        outer.addLayout(hint_layout)

        # Wire ---------------------------------------------
        qconnect(self.btn_pick.clicked, self._on_pick_file)
        qconnect(self.btn_install_ffmpeg.clicked, self._on_install_ffmpeg)
        qconnect(self.btn_play.clicked, self._on_play_pause)
        qconnect(self.combo_speed.currentTextChanged, self._on_speed_changed)
        qconnect(self.slider_pos.sliderPressed, self._on_slider_pressed)
        qconnect(self.slider_pos.sliderReleased, self._on_slider_released)
        qconnect(self.slider_pos.sliderMoved, self._on_slider_moved)
        qconnect(self.btn_set_start.clicked, self._set_start_now)
        qconnect(self.btn_set_end.clicked, self._set_end_now)
        qconnect(self.btn_preview.clicked, self._on_preview)
        qconnect(self.btn_undo.clicked, self._on_undo)
        qconnect(self.btn_cut.clicked, self._on_cut)
        qconnect(self.btn_play_cut.clicked, self._on_play_cut)
        qconnect(self.btn_add_note.clicked, self._on_add_note)
        qconnect(self.btn_cut_and_add.clicked, self._on_cut_and_add)
        qconnect(self.btn_add_queue.clicked, self._on_add_to_queue)
        qconnect(self.btn_queue_play.clicked, self._on_queue_play)
        qconnect(self.btn_queue_remove.clicked, self._on_queue_remove)
        qconnect(self.btn_queue_clear.clicked, self._on_queue_clear)
        qconnect(self.btn_queue_cut_all.clicked, self._on_queue_cut_all)
        qconnect(self.queue_list.itemDoubleClicked, self._on_queue_item_double_clicked)
        qconnect(self.queue_list.currentRowChanged, self._on_queue_item_selected)
        qconnect(self.btn_settings.clicked, self._on_open_settings)

        # Wire nudge & preview buttons
        qconnect(self.btn_nudge_s_m500.clicked, lambda: self._nudge_time(True, -NUDGE_STEP_LARGE_SEC))
        qconnect(self.btn_nudge_s_m100.clicked, lambda: self._nudge_time(True, -NUDGE_STEP_SMALL_SEC))
        qconnect(self.btn_nudge_s_p100.clicked, lambda: self._nudge_time(True, NUDGE_STEP_SMALL_SEC))
        qconnect(self.btn_nudge_s_p500.clicked, lambda: self._nudge_time(True, NUDGE_STEP_LARGE_SEC))
        qconnect(self.btn_nudge_e_m500.clicked, lambda: self._nudge_time(False, -NUDGE_STEP_LARGE_SEC))
        qconnect(self.btn_nudge_e_m100.clicked, lambda: self._nudge_time(False, -NUDGE_STEP_SMALL_SEC))
        qconnect(self.btn_nudge_e_p100.clicked, lambda: self._nudge_time(False, NUDGE_STEP_SMALL_SEC))
        qconnect(self.btn_nudge_e_p500.clicked, lambda: self._nudge_time(False, NUDGE_STEP_LARGE_SEC))
        qconnect(self.btn_play_start.clicked, self._on_preview_start)
        qconnect(self.btn_play_end.clicked, self._on_preview_end)
        qconnect(self.btn_deck.clicked, self._on_pick_deck)
        qconnect(self.btn_notetype.clicked, self._on_pick_notetype)
        qconnect(self.combo_audio_field.currentTextChanged,
                 lambda _: self._render_fields_for_current_notetype())

        # Update region highlight when start/end text changes
        qconnect(self.input_start.textChanged,
                 lambda _: self._update_region_highlight())
        qconnect(self.input_end.textChanged,
                 lambda _: self._update_region_highlight())

        # Drag & drop
        self.setAcceptDrops(True)

    def _update_region_highlight(self) -> None:
        s = parse_time(self.input_start.text())
        e = parse_time(self.input_end.text())
        if s is not None and e is not None and e > s:
            self.slider_pos.set_region(int(s * 1000), int(e * 1000))
        else:
            self.slider_pos.clear_region()

    def _on_waveform_region_changed(self, start_sec: float, end_sec: float) -> None:
        self.input_start.blockSignals(True)
        self.input_end.blockSignals(True)
        self.input_start.setText(fmt_time(start_sec))
        self.input_end.setText(fmt_time(end_sec))
        self.input_start.blockSignals(False)
        self.input_end.blockSignals(False)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    ext = os.path.splitext(url.toLocalFile())[1].lower()
                    if ext in AUDIO_EXTENSIONS:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                ext = os.path.splitext(path)[1].lower()
                if ext in AUDIO_EXTENSIONS:
                    self._load_audio(path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def _setup_player(self) -> None:
        if not HAS_MEDIA:
            self.btn_play.setEnabled(False)
            self.btn_play.setToolTip(tr("no_media_tooltip"))
            return
        self._player = QMediaPlayer(self)
        if QT_MAJOR == 6:
            self._audio_out = QAudioOutput(self)
            self._player.setAudioOutput(self._audio_out)
            qconnect(self._player.errorOccurred, self._on_player_error)
            qconnect(self._player.playbackStateChanged, self._on_player_state)
        else:
            qconnect(self._player.error,
                     lambda *_: self._on_player_error(None, "Playback error."))
            qconnect(self._player.stateChanged, self._on_player_state)
        qconnect(self._player.positionChanged, self._on_player_position)
        qconnect(self._player.durationChanged, self._on_player_duration)

        # Polling timer for stop-at-end-of-region
        self._tick = QTimer(self)
        self._tick.setInterval(TICK_INTERVAL_MS)
        qconnect(self._tick.timeout, self._on_tick)

    def _setup_shortcuts(self) -> None:
        # Single-key shortcuts (Space, [, ], P, Q, C, arrows) are handled
        # in keyPressEvent to avoid conflicts with text input fields.
        bindings = [
            ("Ctrl+Return", self._on_cut_and_add),
            ("Ctrl+Enter", self._on_cut_and_add),
            ("Ctrl+Z", self._on_undo),
            ("Ctrl+W", self.close),
            # Alt shortcuts for global control (when focus is in text fields)
            ("Alt+Space", self._on_play_pause),
            ("Alt+[", self._set_start_now),
            ("Alt+]", self._set_end_now),
            ("Alt+P", self._on_preview),
            ("Alt+S", self._on_preview_start),
            ("Alt+E", self._on_preview_end),
            ("Alt+A", lambda: self._nudge_time(is_start=True, delta_sec=-NUDGE_STEP_SMALL_SEC)),
            ("Alt+Shift+A", lambda: self._nudge_time(is_start=True, delta_sec=-NUDGE_STEP_LARGE_SEC)),
            ("Alt+D", lambda: self._nudge_time(is_start=True, delta_sec=NUDGE_STEP_SMALL_SEC)),
            ("Alt+Shift+D", lambda: self._nudge_time(is_start=True, delta_sec=NUDGE_STEP_LARGE_SEC)),
            ("Alt+J", lambda: self._nudge_time(is_start=False, delta_sec=-NUDGE_STEP_SMALL_SEC)),
            ("Alt+Shift+J", lambda: self._nudge_time(is_start=False, delta_sec=-NUDGE_STEP_LARGE_SEC)),
            ("Alt+L", lambda: self._nudge_time(is_start=False, delta_sec=NUDGE_STEP_SMALL_SEC)),
            ("Alt+Shift+L", lambda: self._nudge_time(is_start=False, delta_sec=NUDGE_STEP_LARGE_SEC)),
        ]
        for key, fn in bindings:
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(fn)

    # ---- Key event dispatch (replaces global QShortcut for single keys) ----

    def _is_focus_on_text_input(self) -> bool:
        w = self.focusWidget()
        return isinstance(w, (QPlainTextEdit, QLineEdit))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if not self._is_focus_on_text_input():
            key = event.key()
            mods = event.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
            shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
            no_mod = mods == Qt.KeyboardModifier.NoModifier

            if key == Qt.Key.Key_Space and no_mod:
                self._on_play_pause()
                return
            if key == Qt.Key.Key_BracketLeft and no_mod:
                self._set_start_now()
                return
            if key == Qt.Key.Key_BracketRight and no_mod:
                self._set_end_now()
                return
            if key == Qt.Key.Key_P and no_mod:
                self._on_preview()
                return
            if key == Qt.Key.Key_Q and no_mod:
                self._on_add_to_queue()
                return
            if key == Qt.Key.Key_C and no_mod:
                self._on_cut()
                return
            if key == Qt.Key.Key_A and (no_mod or shift):
                self._nudge_time(is_start=True, delta_sec=-NUDGE_STEP_LARGE_SEC if shift else -NUDGE_STEP_SMALL_SEC)
                return
            if key == Qt.Key.Key_D and (no_mod or shift):
                self._nudge_time(is_start=True, delta_sec=NUDGE_STEP_LARGE_SEC if shift else NUDGE_STEP_SMALL_SEC)
                return
            if key == Qt.Key.Key_J and (no_mod or shift):
                self._nudge_time(is_start=False, delta_sec=-NUDGE_STEP_LARGE_SEC if shift else -NUDGE_STEP_SMALL_SEC)
                return
            if key == Qt.Key.Key_L and (no_mod or shift):
                self._nudge_time(is_start=False, delta_sec=NUDGE_STEP_LARGE_SEC if shift else NUDGE_STEP_SMALL_SEC)
                return
            if key == Qt.Key.Key_S and no_mod:
                self._on_preview_start()
                return
            if key == Qt.Key.Key_E and no_mod:
                self._on_preview_end()
                return
            # Arrow seek: Right +5s, Left -5s, Shift+ 1s
            if key == Qt.Key.Key_Right and (no_mod or shift):
                self._seek(SEEK_STEP_SMALL_SEC if shift else SEEK_STEP_LARGE_SEC)
                return
            if key == Qt.Key.Key_Left and (no_mod or shift):
                self._seek(-SEEK_STEP_SMALL_SEC if shift else -SEEK_STEP_LARGE_SEC)
                return
        super().keyPressEvent(event)

    def _seek(self, delta_sec: float) -> None:
        if not HAS_MEDIA or not self._src_path:
            return
        pos_ms = self._player.position()
        new_ms = max(0, min(pos_ms + int(delta_sec * 1000),
                            self.slider_pos.maximum()))
        self._player.setPosition(new_ms)
        self.slider_pos.setValue(new_ms)
        self.lbl_time.setText(
            f"{fmt_time(new_ms / 1000.0)} / {fmt_time(self._duration)}"
        )

    # ------------------------- Population ------------------

    def _populate_decks_notetypes(self) -> None:
        col = mw.col
        if col is None:
            return
        cfg = _config()

        # Deck names
        self._deck_names = [d.name for d in col.decks.all_names_and_ids()]
        self._selected_deck = (
            cfg.get("default_deck")
            or col.decks.name(col.decks.get_current_id())
        )
        if self._selected_deck not in self._deck_names and self._deck_names:
            self._selected_deck = self._deck_names[0]
        self.btn_deck.setText(self._selected_deck)

        # Notetype names
        self._notetype_names = [
            n.name for n in col.models.all_names_and_ids()
        ]
        self._selected_notetype = (
            cfg.get("default_notetype") or col.models.current()["name"]
        )
        if (self._selected_notetype not in self._notetype_names
                and self._notetype_names):
            self._selected_notetype = self._notetype_names[0]
        self.btn_notetype.setText(self._selected_notetype)

    def _on_pick_deck(self) -> None:
        # Refresh deck list from Anki
        col = mw.col
        if col:
            self._deck_names = [d.name for d in col.decks.all_names_and_ids()]
        result = DeckSelectDialog.select(
            tr("search_deck_title"),
            self._deck_names,
            self._selected_deck,
            self,
        )
        if result:
            self._selected_deck = result
            self.btn_deck.setText(result)
            # Refresh deck list in case CRUD operations changed it
            if col:
                self._deck_names = [d.name for d in col.decks.all_names_and_ids()]

    def _on_pick_notetype(self) -> None:
        # Refresh notetype list from Anki
        col = mw.col
        if col:
            self._notetype_names = [n.name for n in col.models.all_names_and_ids()]
        result = NoteTypeSelectDialog.select(
            tr("search_notetype_title"),
            self._notetype_names,
            self._selected_notetype,
            self,
        )
        if result and result != self._selected_notetype:
            self._selected_notetype = result
            self.btn_notetype.setText(result)
            self._render_fields_for_current_notetype()
            # Refresh notetype list in case CRUD operations changed it
            if col:
                self._notetype_names = [n.name for n in col.models.all_names_and_ids()]

    def _is_field_pinned(self, field_name: str) -> bool:
        cfg = _config()
        pinned_dict = cfg.get("pinned_fields", {})
        notetype_name = self._selected_notetype or ""
        pinned_list = pinned_dict.get(notetype_name, [])
        return field_name in pinned_list

    def _set_field_pinned(self, field_name: str, pinned: bool) -> None:
        cfg = _config()
        pinned_dict = cfg.get("pinned_fields", {})
        notetype_name = self._selected_notetype or ""
        if notetype_name not in pinned_dict:
            pinned_dict[notetype_name] = []
        
        pinned_list = pinned_dict[notetype_name]
        if pinned:
            if field_name not in pinned_list:
                pinned_list.append(field_name)
        else:
            if field_name in pinned_list:
                pinned_list.remove(field_name)
                
        pinned_dict[notetype_name] = pinned_list
        cfg["pinned_fields"] = pinned_dict
        _save_config(cfg)

    def _render_fields_for_current_notetype(self) -> None:
        col = mw.col
        if col is None:
            return
        nt_name = self._selected_notetype
        model = col.models.by_name(nt_name) if nt_name else col.models.current()
        if model is None:
            return

        field_names = [f["name"] for f in model["flds"]]

        # Update audio field combo
        prev_audio = self.combo_audio_field.currentText()
        self.combo_audio_field.blockSignals(True)
        self.combo_audio_field.clear()
        self.combo_audio_field.addItems(field_names)
        cfg_audio = _config().get("audio_field") or "Audio"
        restore = prev_audio if prev_audio in field_names else None
        if not restore:
            for f in field_names:
                if f.lower() == cfg_audio.lower():
                    restore = f
                    break
        if not restore:
            for f in field_names:
                low = f.lower()
                if "audio" in low or "sound" in low:
                    restore = f
                    break
        if restore:
            idx = self.combo_audio_field.findText(restore)
            if idx >= 0:
                self.combo_audio_field.setCurrentIndex(idx)
        self.combo_audio_field.blockSignals(False)

        audio_field = self.combo_audio_field.currentText()

        # Save field content before rebuilding
        saved = {name: ed.toPlainText() for name, ed in self._field_editors.items()}

        # Remove old editors
        while self.fields_layout.rowCount():
            self.fields_layout.removeRow(0)
        self._field_editors.clear()

        # Determine alignment flags and cursor types based on Qt version
        if QT_MAJOR == 6:
            align_right = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight
            align_center = Qt.AlignmentFlag.AlignVCenter
            pointing_hand = Qt.CursorShape.PointingHandCursor
        else:
            align_right = Qt.AlignVCenter | Qt.AlignRight
            align_center = Qt.AlignVCenter
            pointing_hand = Qt.PointingHandCursor

        for fname in field_names:
            editor = QPlainTextEdit()
            editor.setMaximumHeight(58)
            editor.setPlaceholderText(tr("field_placeholder", field=fname))
            if fname in saved:
                editor.setPlainText(saved[fname])
            self._field_editors[fname] = editor

            is_audio = (fname == audio_field)
            is_pinned = self._is_field_pinned(fname)

            lbl_widget = QWidget()
            lbl_layout = QHBoxLayout(lbl_widget)
            lbl_layout.setContentsMargins(0, 0, 5, 0)
            lbl_layout.setSpacing(4)

            lbl_text = QLabel(tr("label_audio_field_target", field=fname) if is_audio else f"{fname}:")
            if is_audio:
                lbl_text.setStyleSheet(STYLING_ACTIVE_LABEL)

            pin_btn = QPushButton("📌")
            pin_btn.setCheckable(True)
            pin_btn.setFlat(True)
            pin_btn.setChecked(is_pinned)
            pin_btn.setFixedSize(20, 20)
            pin_btn.setCursor(pointing_hand)
            pin_btn.setToolTip("Keep field content after adding note (Pin)")

            def update_style(checked, b=pin_btn):
                if checked:
                    b.setStyleSheet("""
                        QPushButton {
                            border: 1px solid #0078d7;
                            background-color: rgba(0, 120, 215, 0.15);
                            border-radius: 3px;
                            padding: 0;
                            margin: 0;
                        }
                    """)
                else:
                    b.setStyleSheet("""
                        QPushButton {
                            border: none;
                            background-color: transparent;
                            padding: 0;
                            margin: 0;
                        }
                        QPushButton:hover {
                            background-color: rgba(0, 0, 0, 0.05);
                            border-radius: 3px;
                        }
                    """)

            update_style(is_pinned)

            qconnect(pin_btn.clicked, lambda checked, fn=fname, b=pin_btn: (
                update_style(checked, b),
                self._set_field_pinned(fn, checked)
            ))

            lbl_layout.addWidget(lbl_text, 1, align_right)
            lbl_layout.addWidget(pin_btn, 0, align_center)

            self.fields_layout.addRow(lbl_widget, editor)

    # ------------------------- File picking ----------------

    def _on_pick_file(self) -> None:
        self.activateWindow()
        last_dir = _config().get("last_audio_dir") or ""
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("btn_select_file"),
            last_dir,
            "Audio (*.mp3 *.wav *.m4a *.ogg *.flac *.aac *.opus *.wma);;"
            "All files (*)",
        )
        if not path:
            return
        cfg = _config()
        cfg["last_audio_dir"] = os.path.dirname(path)
        _save_config(cfg)
        self._load_audio(path)

    def _load_audio(self, path: str) -> None:
        if not os.path.exists(path):
            showWarning(tr("file_not_found", path=path), parent=self)
            return
        # Stop current playback
        if HAS_MEDIA:
            self._player.stop()
            self._stop_at_ms = -1

        # Clear old waveform data immediately
        self.slider_pos.set_waveform_data([])

        # Get duration via ffprobe/ffmpeg
        try:
            self._duration = _probe_duration(path) or 0.0
        except FFmpegNotFoundError:
            self._duration = 0.0
        except Exception:
            traceback.print_exc()
            self._duration = 0.0

        self._src_path = path
        self.lbl_file.setText(os.path.basename(path))
        self.lbl_file.setStyleSheet(STYLING_LBL_FILE_LOADED)

        # Reset region inputs
        self.input_start.setText("0:00.00")
        self.input_end.setText(fmt_time(self._duration))

        # Reset pending cut
        self._pending_cut_file = ""
        self.btn_play_cut.setEnabled(False)
        self.btn_add_note.setEnabled(False)

        # Set up slider
        total_ms = int(round(self._duration * 1000))
        self.slider_pos.setRange(0, total_ms if total_ms > 0 else 0)
        self.slider_pos.setValue(0)
        self.lbl_time.setText(f"0:00.00 / {fmt_time(self._duration)}")

        # Load into player
        if HAS_MEDIA:
            url = QUrl.fromLocalFile(path)
            if QT_MAJOR == 6:
                self._player.setSource(url)
            else:
                self._player.setMedia(QMediaContent(url))
            self._loaded_player_path = path
        self._set_audio_loaded(True)

        # Load waveform in background
        def get_waveform():
            try:
                return extract_waveform(path)
            except Exception:
                traceback.print_exc()
                return []

        def on_waveform_done(future):
            try:
                data = future.result()
            except Exception:
                traceback.print_exc()
                data = []
            if self._src_path == path:
                self.slider_pos.set_waveform_data(data)

        mw.taskman.run_in_background(get_waveform, on_waveform_done)

    def _set_audio_loaded(self, loaded: bool) -> None:
        self.btn_play.setEnabled(loaded and HAS_MEDIA)
        self.combo_speed.setEnabled(loaded and HAS_MEDIA)
        self.slider_pos.setEnabled(loaded and HAS_MEDIA)
        self.btn_set_start.setEnabled(loaded)
        self.btn_set_end.setEnabled(loaded)
        self.btn_preview.setEnabled(loaded and HAS_MEDIA)
        self.btn_cut.setEnabled(loaded)
        self.btn_cut_and_add.setEnabled(loaded)

        # Toggle nudge buttons and hear start/end buttons
        for btn in (
            self.btn_nudge_s_m500, self.btn_nudge_s_m100,
            self.btn_nudge_s_p100, self.btn_nudge_s_p500,
            self.btn_nudge_e_m500, self.btn_nudge_e_m100,
            self.btn_nudge_e_p100, self.btn_nudge_e_p500,
        ):
            btn.setEnabled(loaded)
        self.btn_play_start.setEnabled(loaded and HAS_MEDIA)
        self.btn_play_end.setEnabled(loaded and HAS_MEDIA)

        if loaded and HAS_MEDIA:
            self._on_speed_changed(self.combo_speed.currentText())

    # ------------------------- Playback --------------------

    def _read_region_silent(self) -> Optional[tuple[float, float]]:
        s = parse_time(self.input_start.text())
        e = parse_time(self.input_end.text())
        if s is not None and e is not None and e > s:
            return s, e
        return None

    def _ensure_original_source_loaded(self) -> None:
        """Ensure the main source audio is loaded in the player."""
        if not HAS_MEDIA or not self._src_path:
            return

        is_loaded = False
        if QT_MAJOR == 6:
            current_src = self._player.source()
            url = QUrl.fromLocalFile(self._src_path)
            if current_src == url:
                is_loaded = True
        else:
            if getattr(self, "_loaded_player_path", "") == self._src_path:
                is_loaded = True

        if not is_loaded:
            self._player.stop()
            self._stop_at_ms = -1
            
            url = QUrl.fromLocalFile(self._src_path)
            if QT_MAJOR == 6:
                self._player.setSource(url)
            else:
                self._player.setMedia(QMediaContent(url))
            self._loaded_player_path = self._src_path

            # Wait synchronously (using event loop) until media is ready
            from aqt.qt import QEventLoop
            loop = QEventLoop()

            def check_status(*args):
                status = self._player.mediaStatus()
                if QT_MAJOR == 6:
                    ready = status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia)
                    invalid = status == QMediaPlayer.MediaStatus.InvalidMedia
                else:
                    ready = status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia)
                    invalid = status == QMediaPlayer.InvalidMedia
                if ready or invalid:
                    loop.quit()

            self._player.mediaStatusChanged.connect(check_status)

            safety_timer = QTimer(self)
            safety_timer.setSingleShot(True)
            qconnect(safety_timer.timeout, loop.quit)
            safety_timer.start(1500)

            loop.exec()

            try:
                self._player.mediaStatusChanged.disconnect(check_status)
            except Exception:
                pass
            safety_timer.stop()

    def _on_play_pause(self) -> None:
        if not HAS_MEDIA or not self._src_path:
            return
        self._ensure_original_source_loaded()
        if QT_MAJOR == 6:
            playing = (
                self._player.playbackState()
                == QMediaPlayer.PlaybackState.PlayingState
            )
        else:
            playing = self._player.state() == QMediaPlayer.PlayingState
        if playing:
            self._player.pause()
            self._stop_at_ms = -1
        else:
            region = self._read_region_silent()
            if region:
                start, end = region
                start_ms = int(round(start * 1000))
                end_ms = int(round(end * 1000))
                current_pos = self._player.position()
                if current_pos < start_ms or current_pos >= end_ms - 100:
                    self._player.setPosition(start_ms)
                self._stop_at_ms = end_ms
            else:
                self._stop_at_ms = -1
            self._player.play()
            self._tick.start()

    def _on_player_state(self, *_args) -> None:
        if QT_MAJOR == 6:
            playing = (
                self._player.playbackState()
                == QMediaPlayer.PlaybackState.PlayingState
            )
        else:
            playing = self._player.state() == QMediaPlayer.PlayingState
        self.btn_play.setText(tr("btn_pause") if playing else tr("btn_play"))
        if not playing:
            self._stop_at_ms = -1
            self._tick.stop()

    def _on_player_position(self, ms: int) -> None:
        if not self._is_seeking_via_user:
            self.slider_pos.setValue(ms)
        self.lbl_time.setText(
            f"{fmt_time(ms / 1000.0)} / {fmt_time(self._duration)}"
        )

    def _on_player_duration(self, ms: int) -> None:
        if ms and ms > self.slider_pos.maximum():
            self.slider_pos.setRange(0, ms)
            if not self._duration:
                self._duration = ms / 1000.0
                self.input_end.setText(fmt_time(self._duration))
                self.lbl_time.setText(
                    f"0:00.00 / {fmt_time(self._duration)}"
                )

    def _on_player_error(self, *_args) -> None:
        msg = ""
        try:
            msg = self._player.errorString()
        except Exception:
            pass
        if msg:
            tooltip(tr("player_error", error=msg), parent=self)

    def _on_tick(self) -> None:
        if self._stop_at_ms >= 0 and self._player.position() >= self._stop_at_ms:
            self._player.pause()
            self._stop_at_ms = -1

    def _on_slider_pressed(self) -> None:
        self._is_seeking_via_user = True

    def _on_slider_released(self) -> None:
        if HAS_MEDIA:
            self._player.setPosition(self.slider_pos.value())
        self._is_seeking_via_user = False

    def _on_slider_moved(self, ms: int) -> None:
        self.lbl_time.setText(
            f"{fmt_time(ms / 1000.0)} / {fmt_time(self._duration)}"
        )

    # ------------------------- Region --------------------

    def _current_pos_seconds(self) -> float:
        if HAS_MEDIA and self._src_path:
            return self._player.position() / 1000.0
        return self.slider_pos.value() / 1000.0

    def _set_start_now(self) -> None:
        if not self._src_path:
            return
        pos = max(0.0, self._current_pos_seconds() - REACTION_OFFSET_SEC)
        self.input_start.setText(fmt_time(pos))

    def _set_end_now(self) -> None:
        if not self._src_path:
            return
        pos = min(self._duration, self._current_pos_seconds() + REACTION_OFFSET_SEC)
        self.input_end.setText(fmt_time(pos))

    def _read_region(self) -> Optional[tuple]:
        s = parse_time(self.input_start.text())
        e = parse_time(self.input_end.text())
        if s is None or e is None:
            tooltip(tr("invalid_time_format"), parent=self)
            return None
        if e <= s:
            tooltip(tr("invalid_region"), parent=self)
            return None
        return s, e

    def _on_preview(self) -> None:
        if not HAS_MEDIA or not self._src_path:
            return
        self._ensure_original_source_loaded()
        region = self._read_region()
        if region is None:
            return
        start, end = region
        self._stop_at_ms = int(round(end * 1000))
        self._player.setPosition(int(round(start * 1000)))
        self._player.play()
        self._tick.start()

    def _nudge_time(self, is_start: bool, delta_sec: float) -> None:
        if not self._src_path:
            return
        input_widget = self.input_start if is_start else self.input_end
        val = parse_time(input_widget.text())
        if val is None:
            return
        new_val = max(0.0, min(val + delta_sec, self._duration))
        input_widget.setText(fmt_time(new_val))

        # Auto hear on nudge
        if HAS_MEDIA:
            self._ensure_original_source_loaded()
            if is_start:
                # Play segment from start point
                self._stop_at_ms = int(round((new_val + PREVIEW_DURATION_SEC) * 1000))
                self._player.setPosition(int(round(new_val * 1000)))
            else:
                # Play segment leading up to end point
                start_play = max(0.0, new_val - PREVIEW_DURATION_SEC)
                self._stop_at_ms = int(round(new_val * 1000))
                self._player.setPosition(int(round(start_play * 1000)))
            self._player.play()
            self._tick.start()

    def _on_preview_start(self) -> None:
        if not HAS_MEDIA or not self._src_path:
            return
        self._ensure_original_source_loaded()
        start = parse_time(self.input_start.text())
        if start is None:
            tooltip(tr("invalid_time_format"), parent=self)
            return
        # Play preview from start
        self._stop_at_ms = int(round((start + PREVIEW_DURATION_SEC) * 1000))
        self._player.setPosition(int(round(start * 1000)))
        self._player.play()
        self._tick.start()

    def _on_preview_end(self) -> None:
        if not HAS_MEDIA or not self._src_path:
            return
        self._ensure_original_source_loaded()
        end = parse_time(self.input_end.text())
        if end is None:
            tooltip(tr("invalid_time_format"), parent=self)
            return
        # Play preview leading up to end
        start = max(0.0, end - PREVIEW_DURATION_SEC)
        self._stop_at_ms = int(round(end * 1000))
        self._player.setPosition(int(round(start * 1000)))
        self._player.play()
        self._tick.start()

    def _on_speed_changed(self, text: str) -> None:
        if not HAS_MEDIA or not hasattr(self, "_player"):
            return
        try:
            rate = float(text.replace("x", ""))
            self._player.setPlaybackRate(rate)
        except Exception:
            traceback.print_exc()

    # ------------------------- Cut (only cut, no note) ----

    def _on_cut(self) -> None:
        if not self._src_path:
            tooltip(tr("select_audio_first"), parent=self)
            return
        region = self._read_region()
        if region is None:
            return
        start, end = region

        # Duplicate region warning
        if self._cut_history_file == self._src_path:
            for prev_s, prev_e in self._cut_history:
                overlap = min(end, prev_e) - max(start, prev_s)
                min_len = min(end - start, prev_e - prev_s)
                if min_len > 0 and overlap / min_len > 0.8:
                    ans = QMessageBox.question(
                        self,
                        tr("duplicate_title"),
                        tr("duplicate_confirm",
                           start=fmt_time(start), end=fmt_time(end),
                           pct=int(overlap / min_len * 100),
                           prev_start=fmt_time(prev_s),
                           prev_end=fmt_time(prev_e)),
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No,
                    )
                    if ans != QMessageBox.StandardButton.Yes:
                        return
                    break

        # Check ffmpeg
        try:
            _ffmpeg_binary()
        except FFmpegNotFoundError as exc:
            self._refresh_ffmpeg_status()
            if sys.platform.startswith("win"):
                ans = QMessageBox.question(
                    self,
                    tr("ffmpeg_not_installed_title"),
                    tr("ffmpeg_not_installed_ask", error=exc),
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                )
                if ans == QMessageBox.StandardButton.Yes and install_ffmpeg_windows(self):
                    self._refresh_ffmpeg_status()
                else:
                    return
            else:
                showWarning(str(exc), parent=self)
                return

        self.btn_cut.setEnabled(False)
        self.btn_cut.setText(tr("btn_cutting"))
        media_dir = mw.col.media.dir()

        def _bg_cut():
            try:
                filename = _cut_audio_to_media(
                    src_path=self._src_path,
                    start=start, end=end,
                    media_dir=media_dir,
                )
                mw.taskman.run_on_main(
                    lambda: self._finish_cut(filename, start, end)
                )
            except Exception:
                tb = traceback.format_exc()
                mw.taskman.run_on_main(lambda: self._finish_cut_error(tb))

        threading.Thread(target=_bg_cut, daemon=True).start()

    def _finish_cut(self, media_filename: str,
                    start: float, end: float) -> None:
        self.btn_cut.setEnabled(True)
        self.btn_cut.setText(tr("btn_cut"))

        self._pending_cut_file = media_filename
        self.btn_play_cut.setEnabled(HAS_MEDIA)
        self.btn_add_note.setEnabled(True)

        # Track for duplicate detection
        if self._cut_history_file != self._src_path:
            self._cut_history.clear()
            self._cut_history_file = self._src_path
        self._cut_history.append((start, end))

        # Determine target editor: currently focused field or default audio field
        target_editor = None
        focused = self.focusWidget()
        for fname, ed in self._field_editors.items():
            if ed == focused:
                target_editor = ed
                break

        if target_editor is None:
            audio_field = self.combo_audio_field.currentText()
            if audio_field in self._field_editors:
                target_editor = self._field_editors[audio_field]

        if target_editor:
            sound_tag = f"[sound:{media_filename}]"
            cursor = target_editor.textCursor()
            if target_editor.toPlainText().strip():
                if cursor.position() > 0 and not cursor.atBlockStart():
                    cursor.insertText(" ")
                cursor.insertText(sound_tag)
            else:
                target_editor.setPlainText(sound_tag)
            target_editor.setFocus()

        # Track for file-only undo
        self._last_audio_file = media_filename
        self._last_note_id = None
        self.btn_undo.setEnabled(True)

        tooltip(tr("cut_to_field_success", filename=media_filename),
                parent=self, period=1800)

    def _finish_cut_error(self, tb: str) -> None:
        self.btn_cut.setEnabled(True)
        self.btn_cut.setText(tr("btn_cut"))
        showWarning(tr("cut_error", error=tb), parent=self)

    # ------------------------- Play cut result ------------

    def _on_play_cut(self) -> None:
        if not HAS_MEDIA or not self._pending_cut_file:
            return
        cut_path = os.path.join(mw.col.media.dir(), self._pending_cut_file)
        if not os.path.exists(cut_path):
            return
        self._stop_at_ms = -1
        url = QUrl.fromLocalFile(cut_path)
        if QT_MAJOR == 6:
            self._player.setSource(url)
        else:
            self._player.setMedia(QMediaContent(url))
        self._loaded_player_path = cut_path
        self._player.play()
        self._tick.start()

    # ------------------------- Add Note -------------------

    def _on_add_note(self) -> None:
        if not self._pending_cut_file:
            tooltip(tr("cut_first"), parent=self)
            return

        deck_name = self._selected_deck or None
        notetype_name = self._selected_notetype or None
        audio_field_name = self.combo_audio_field.currentText()
        fields = {
            name: ed.toPlainText() for name, ed in self._field_editors.items()
        }
        tags = self.input_tags.text().strip()

        mw.checkpoint("Add Audio Note")
        try:
            nid = _add_note(
                deck_name=deck_name,
                notetype_name=notetype_name,
                fields=fields,
                audio_filename=self._pending_cut_file,
                audio_field_name=audio_field_name,
                tags=tags,
            )
        except Exception as exc:
            traceback.print_exc()
            showWarning(tr("note_add_error", error=exc), parent=self)
            return

        if nid:
            # Track for undo
            self._last_note_id = nid
            self._last_audio_file = self._pending_cut_file
            self.btn_undo.setEnabled(True)

            # Save config
            cfg = _config()
            cfg["default_deck"] = deck_name or ""
            cfg["default_notetype"] = notetype_name or ""
            cfg["audio_field"] = audio_field_name
            cfg["last_tags"] = tags
            _save_config(cfg)

            # Reset pending cut
            self._pending_cut_file = ""
            self.btn_play_cut.setEnabled(False)
            self.btn_add_note.setEnabled(False)

            # Reload original audio into player
            if HAS_MEDIA and self._src_path:
                url = QUrl.fromLocalFile(self._src_path)
                if QT_MAJOR == 6:
                    self._player.setSource(url)
                else:
                    self._player.setMedia(QMediaContent(url))
                self._loaded_player_path = self._src_path

            try:
                mw.reset()
            except Exception:
                pass
            tooltip(
                tr("note_added", filename=self._last_audio_file),
                parent=self, period=1800,
            )
            # Clear text fields, keep audio + region (respecting pinned fields)
            for fname, editor in self._field_editors.items():
                if not self._is_field_pinned(fname):
                    editor.clear()
            self.input_tags.clear()
        else:
            showWarning(tr("note_add_failed"), parent=self)

    # ------------------------- Cut & Add (one step) ------

    def _on_cut_and_add(self) -> None:
        """Cut audio and immediately create a note — single-card workflow."""
        if not self._src_path:
            tooltip(tr("select_audio_first"), parent=self)
            return
        region = self._read_region()
        if region is None:
            return
        start, end = region

        # Duplicate region warning
        if self._cut_history_file == self._src_path:
            for prev_s, prev_e in self._cut_history:
                overlap = min(end, prev_e) - max(start, prev_s)
                min_len = min(end - start, prev_e - prev_s)
                if min_len > 0 and overlap / min_len > 0.8:
                    ans = QMessageBox.question(
                        self,
                        tr("duplicate_title"),
                        tr("duplicate_confirm",
                           start=fmt_time(start), end=fmt_time(end),
                           pct=int(overlap / min_len * 100),
                           prev_start=fmt_time(prev_s),
                           prev_end=fmt_time(prev_e)),
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No,
                    )
                    if ans != QMessageBox.StandardButton.Yes:
                        return
                    break

        # Check ffmpeg
        try:
            _ffmpeg_binary()
        except FFmpegNotFoundError as exc:
            self._refresh_ffmpeg_status()
            if sys.platform.startswith("win"):
                ans = QMessageBox.question(
                    self,
                    tr("ffmpeg_not_installed_title"),
                    tr("ffmpeg_not_installed_ask", error=exc),
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                )
                if ans == QMessageBox.StandardButton.Yes and install_ffmpeg_windows(self):
                    self._refresh_ffmpeg_status()
                else:
                    return
            else:
                showWarning(str(exc), parent=self)
                return

        # Capture all note params before going async
        deck_name = self._selected_deck or None
        notetype_name = self._selected_notetype or None
        audio_field_name = self.combo_audio_field.currentText()
        fields = {
            name: ed.toPlainText() for name, ed in self._field_editors.items()
        }
        tags = self.input_tags.text().strip()
        media_dir = mw.col.media.dir()

        self.btn_cut_and_add.setEnabled(False)
        self.btn_cut.setEnabled(False)
        self.btn_cut_and_add.setText(tr("btn_cutting"))

        def _bg():
            try:
                filename = _cut_audio_to_media(
                    src_path=self._src_path,
                    start=start, end=end,
                    media_dir=media_dir,
                )
                mw.taskman.run_on_main(lambda: self._finish_cut_and_add(
                    filename, deck_name, notetype_name, audio_field_name,
                    fields, tags, start, end,
                ))
            except Exception:
                tb = traceback.format_exc()
                mw.taskman.run_on_main(lambda: self._finish_cut_and_add_error(tb))

        threading.Thread(target=_bg, daemon=True).start()

    def _finish_cut_and_add(
        self,
        media_filename: str,
        deck_name: Optional[str],
        notetype_name: Optional[str],
        audio_field_name: str,
        fields: dict,
        tags: str,
        start: float,
        end: float,
    ) -> None:
        self.btn_cut_and_add.setEnabled(True)
        self.btn_cut_and_add.setText(tr("btn_cut_and_add"))
        self.btn_cut.setEnabled(True)

        mw.checkpoint("Add Audio Note")
        try:
            nid = _add_note(
                deck_name=deck_name,
                notetype_name=notetype_name,
                fields=fields,
                audio_filename=media_filename,
                audio_field_name=audio_field_name,
                tags=tags,
            )
        except Exception as exc:
            traceback.print_exc()
            showWarning(tr("note_add_error", error=exc), parent=self)
            return

        if nid:
            self._last_note_id = nid
            self._last_audio_file = media_filename
            self.btn_undo.setEnabled(True)

            if self._cut_history_file != self._src_path:
                self._cut_history.clear()
                self._cut_history_file = self._src_path
            self._cut_history.append((start, end))

            cfg = _config()
            cfg["default_deck"] = deck_name or ""
            cfg["default_notetype"] = notetype_name or ""
            cfg["audio_field"] = audio_field_name
            cfg["last_tags"] = tags
            _save_config(cfg)

            try:
                mw.reset()
            except Exception:
                pass
            tooltip(
                tr("note_added", filename=media_filename),
                parent=self, period=1800,
            )
            # Clear text fields (except pinned ones)
            for fname, editor in self._field_editors.items():
                if not self._is_field_pinned(fname):
                    editor.clear()
            self.input_tags.clear()
        else:
            showWarning(tr("note_add_failed"), parent=self)

    def _finish_cut_and_add_error(self, tb: str) -> None:
        self.btn_cut_and_add.setEnabled(True)
        self.btn_cut_and_add.setText(tr("btn_cut_and_add"))
        self.btn_cut.setEnabled(True)
        showWarning(tr("cut_error", error=tb), parent=self)

    # ------------------------- Undo ----------------------

    def _on_undo(self) -> None:
        if self._last_note_id is None and not self._last_audio_file and not self._last_batch_files:
            tooltip(tr("undo_nothing"), parent=self)
            return

        if self._last_note_id is not None:
            audio_file = self._last_audio_file
            nid = self._last_note_id
            ans = QMessageBox.question(
                self,
                tr("undo_confirm_title"),
                tr("undo_confirm", nid=nid, filename=audio_file),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

            try:
                _undo_last_note(audio_file)
                if self._cut_history:
                    self._cut_history.pop()
            except Exception as exc:
                traceback.print_exc()
                showWarning(tr("undo_error", error=exc), parent=self)
                return
            self._last_note_id = None
            self._last_audio_file = ""
            tooltip(tr("undo_success"), parent=self, period=1800)
        elif self._last_batch_files:
            count = len(self._last_batch_files)
            ans = QMessageBox.question(
                self,
                tr("undo_confirm_title"),
                tr("undo_confirm_batch_files", count=count),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

            media_dir = mw.col.media.dir() if (mw and mw.col) else None
            if media_dir:
                for audio_file in self._last_batch_files:
                    if audio_file:
                        audio_path = os.path.join(media_dir, audio_file)
                        if os.path.exists(audio_path):
                            try:
                                os.remove(audio_path)
                            except OSError:
                                pass

            # Restore queue items back to uncut state
            for item in self._batch_queue:
                if item[2] in self._last_batch_files:
                    item[2] = None
            self._refresh_queue_ui()

            for _ in range(count):
                if self._cut_history:
                    self._cut_history.pop()
            self._last_batch_files = []
            tooltip(tr("undo_success_batch_files"), parent=self, period=1800)
        else:
            audio_file = self._last_audio_file
            ans = QMessageBox.question(
                self,
                tr("undo_confirm_title"),
                tr("undo_confirm_file_only", filename=audio_file),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return

            media_dir = mw.col.media.dir() if (mw and mw.col) else None
            if media_dir and audio_file:
                audio_path = os.path.join(media_dir, audio_file)
                if os.path.exists(audio_path):
                    try:
                        os.remove(audio_path)
                    except OSError:
                        pass
            if self._cut_history:
                self._cut_history.pop()
            self._last_audio_file = ""
            tooltip(tr("undo_success_file_only"), parent=self, period=1800)

        self.btn_undo.setEnabled(False)
        try:
            mw.reset()
        except Exception:
            pass

    # ------------------------- Batch queue ----------------

    def _on_add_to_queue(self) -> None:
        region = self._read_region()
        if region is None:
            return
        start, end = region
        self._batch_queue.append([start, end, None])
        self._refresh_queue_ui()
        tooltip(
            tr("queue_added", start=fmt_time(start), end=fmt_time(end)),
            parent=self, period=1200,
        )

    def _on_queue_remove(self) -> None:
        row = self.queue_list.currentRow()
        if 0 <= row < len(self._batch_queue):
            self._batch_queue.pop(row)
            self._refresh_queue_ui()

    def _on_queue_clear(self) -> None:
        if not self._batch_queue:
            return
        self._batch_queue.clear()
        self._refresh_queue_ui()

    def _refresh_queue_ui(self) -> None:
        self.queue_list.clear()
        for i, item in enumerate(self._batch_queue):
            s, e, filename = item
            text = f"{i + 1}. "
            if filename is None:
                text += tr("queue_uncut", start=fmt_time(s), end=fmt_time(e))
            else:
                text += tr("queue_cut", start=fmt_time(s), end=fmt_time(e)) + f" -> [sound:{filename}]"
            self.queue_list.addItem(text)
        count = len(self._batch_queue)
        self.queue_box.setTitle(tr("queue_title", count=count))
        self.queue_box.setVisible(count > 0)
        self._update_waveform_queued_regions()

    def _update_waveform_queued_regions(self) -> None:
        regions_ms = [(int(s * 1000), int(e * 1000)) for s, e, _ in self._batch_queue]
        self.slider_pos.set_queued_regions(regions_ms)

    def _on_queue_cut_all(self) -> None:
        if not self._batch_queue or not self._src_path:
            return

        try:
            _ffmpeg_binary()
        except FFmpegNotFoundError as exc:
            self._refresh_ffmpeg_status()
            showWarning(str(exc), parent=self)
            return

        queue = list(self._batch_queue)
        media_dir = mw.col.media.dir()
        src = self._src_path

        self.btn_queue_cut_all.setEnabled(False)
        self.btn_cut.setEnabled(False)
        self.btn_queue_cut_all.setText(
            tr("batch_progress", done=0, total=len(queue))
        )

        def _bg_batch():
            results = []
            for i, item in enumerate(queue):
                start, end, filename = item
                if filename is not None:
                    results.append((filename, start, end, None))
                else:
                    try:
                        filename = _cut_audio_to_media(
                            src_path=src, start=start, end=end,
                            media_dir=media_dir,
                        )
                        results.append((filename, start, end, None))
                    except Exception:
                        results.append((None, start, end, traceback.format_exc()))
                mw.taskman.run_on_main(
                    lambda n=i + 1: self.btn_queue_cut_all.setText(
                        tr("batch_progress", done=n, total=len(queue))
                    )
                )
            mw.taskman.run_on_main(lambda: self._finish_batch(results))

        threading.Thread(target=_bg_batch, daemon=True).start()

    def _finish_batch(self, results: list) -> None:
        self.btn_queue_cut_all.setEnabled(True)
        self.btn_queue_cut_all.setText(tr("btn_queue_cut_all"))
        self.btn_cut.setEnabled(True)

        ok_count = 0
        err_count = 0

        for i, (filename, start, end, err) in enumerate(results):
            if err or not filename:
                err_count += 1
                if i < len(self._batch_queue):
                    self._batch_queue[i][2] = None
            else:
                ok_count += 1
                if i < len(self._batch_queue):
                    self._batch_queue[i][2] = filename
                if self._cut_history_file != self._src_path:
                    self._cut_history.clear()
                    self._cut_history_file = self._src_path
                self._cut_history.append((start, end))

        self._refresh_queue_ui()

        # Track batch files for undo
        self._last_batch_files = [filename for filename, start, end, err in results if filename and not err]
        self._last_note_id = None
        if self._last_batch_files:
            self._last_audio_file = ""
            self.btn_undo.setEnabled(True)

        if err_count:
            msg = tr("batch_cut_done_errors", ok=ok_count, errors=err_count)
        else:
            msg = tr("batch_cut_done", ok=ok_count)
        tooltip(msg, parent=self, period=2500)

    def _on_queue_item_double_clicked(self, item) -> None:
        row = self.queue_list.row(item)
        if 0 <= row < len(self._batch_queue):
            s, e, filename = self._batch_queue[row]
            if filename is None:
                tooltip(tr("queue_warn_cut_first"), parent=self)
                return

            target_editor = None
            focused = self.focusWidget()
            for fname, ed in self._field_editors.items():
                if ed == focused:
                    target_editor = ed
                    break

            if target_editor is None:
                audio_field = self.combo_audio_field.currentText()
                if audio_field in self._field_editors:
                    target_editor = self._field_editors[audio_field]

            if target_editor:
                sound_tag = f"[sound:{filename}]"
                cursor = target_editor.textCursor()
                if target_editor.toPlainText().strip():
                    if cursor.position() > 0 and not cursor.atBlockStart():
                        cursor.insertText(" ")
                    cursor.insertText(sound_tag)
                else:
                    target_editor.setPlainText(sound_tag)
                target_editor.setFocus()
                tooltip(tr("queue_insert_success"), parent=self, period=1200)

    # ------------------------- Settings -------------------

    def _on_open_settings(self) -> None:
        dlg = SettingsDialog(self)
        if dlg.exec():
            # Refresh audio field combo if the config changed
            self._render_fields_for_current_notetype()
            self._refresh_ffmpeg_status()

    # ------------------------- Queue selection & play ------

    def _on_queue_item_selected(self, row: int) -> None:
        """Single-click on queue item: highlight its region on the waveform."""
        if row < 0 or row >= len(self._batch_queue):
            return
        s, e, _filename = self._batch_queue[row]
        # Update region on waveform
        self.slider_pos.set_region(int(s * 1000), int(e * 1000))
        # Update start/end input fields
        self.input_start.blockSignals(True)
        self.input_end.blockSignals(True)
        self.input_start.setText(fmt_time(s))
        self.input_end.setText(fmt_time(e))
        self.input_start.blockSignals(False)
        self.input_end.blockSignals(False)

    def _on_queue_play(self) -> None:
        """Play the currently selected queue item (always preview from source audio to match playhead)."""
        row = self.queue_list.currentRow()
        if row < 0 or row >= len(self._batch_queue):
            tooltip(tr("queue_no_selection"), parent=self)
            return
        s, e, _filename = self._batch_queue[row]

        if not HAS_MEDIA or not self._src_path:
            return

        self._ensure_original_source_loaded()

        self._stop_at_ms = int(round(e * 1000))
        self._player.setPosition(int(round(s * 1000)))
        self._player.play()
        self._tick.start()
        tooltip(tr("queue_preview_uncut"), parent=self, period=1000)
