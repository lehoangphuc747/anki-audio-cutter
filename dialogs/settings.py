# -*- coding: utf-8 -*-
"""
SettingsDialog containing configuration panels for Audio Card Cutter.
"""
import sys as _sys
import threading
import traceback
from typing import Optional

from aqt import mw
from aqt.qt import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, Qt, qconnect
)

from .._tr import tr
from ..anki_interop import _config, _save_config
from ..ffmpeg_utils import (
    _ffmpeg_binary, _is_ffmpeg_available, check_ffmpeg_latest_version,
    get_ffmpeg_version, install_ffmpeg_windows, FFmpegNotFoundError
)
from ..constants import STYLING_SETTINGS_TAB, STYLING_SETTINGS_TABLE


class SettingsDialog(QDialog):
    """Settings dialog with tabbed interface."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("settings_title"))
        self.setMinimumSize(520, 420)
        self._cfg = _config()

        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(STYLING_SETTINGS_TAB)

        self._tabs.addTab(self._build_general_tab(), tr("settings_tab_general"))
        self._tabs.addTab(self._build_shortcuts_tab(), tr("settings_tab_shortcuts"))
        self._tabs.addTab(self._build_ffmpeg_tab(), tr("settings_tab_ffmpeg"))
        layout.addWidget(self._tabs)

        # OK / Cancel
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_ok = QPushButton("OK")
        self._btn_cancel = QPushButton(tr("ffmpeg_cancel"))
        btn_row.addWidget(self._btn_ok)
        btn_row.addWidget(self._btn_cancel)
        layout.addLayout(btn_row)

        qconnect(self._btn_ok.clicked, self._on_save)
        qconnect(self._btn_cancel.clicked, self.reject)

    def _build_general_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        self._combo_format = QComboBox()
        self._combo_format.addItems(["mp3", "ogg", "wav", "m4a", "aac"])
        self._combo_format.setCurrentText(self._cfg.get("output_format", "mp3"))
        form.addRow(tr("settings_general_format"), self._combo_format)

        self._combo_bitrate = QComboBox()
        self._combo_bitrate.addItems(["64k", "96k", "128k", "192k", "256k", "320k"])
        self._combo_bitrate.setCurrentText(self._cfg.get("output_bitrate", "128k"))
        form.addRow(tr("settings_general_bitrate"), self._combo_bitrate)

        self._input_audio_field = QLineEdit()
        self._input_audio_field.setText(self._cfg.get("audio_field", "Audio"))
        self._input_audio_field.setPlaceholderText("Audio")
        form.addRow(tr("settings_general_audio_field"), self._input_audio_field)

        form.addRow(QLabel(""))  # spacer
        return w

    def _build_shortcuts_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        shortcuts = [
            ("Play / Pause", "Space", "Alt+Space"),
            ("Set Start", "[", "Alt+["),
            ("Set End", "]", "Alt+]"),
            ("Preview Region", "P", "Alt+P"),
            ("Hear Start", "S", "Alt+S"),
            ("Hear End", "E", "Alt+E"),
            ("Nudge Start -0.1s", "A", "Alt+A"),
            ("Nudge Start +0.1s", "D", "Alt+D"),
            ("Nudge Start -0.5s", "Shift+A", "Alt+Shift+A"),
            ("Nudge Start +0.5s", "Shift+D", "Alt+Shift+D"),
            ("Nudge End -0.1s", "J", "Alt+J"),
            ("Nudge End +0.1s", "L", "Alt+L"),
            ("Nudge End -0.5s", "Shift+J", "Alt+Shift+J"),
            ("Nudge End +0.5s", "Shift+L", "Alt+Shift+L"),
            ("Seek +5s / +1s", "→ / Shift+→", ""),
            ("Seek -5s / -1s", "← / Shift+←", ""),
            ("Add to Queue", "Q", ""),
            ("Cut to Field", "C", ""),
            ("Cut && Add Note", "Ctrl+Enter", ""),
            ("Undo", "Ctrl+Z", ""),
            ("Close", "Ctrl+W", ""),
        ]

        table = QTableWidget(len(shortcuts), 3)
        table.setHorizontalHeaderLabels([
            tr("settings_shortcuts_action"),
            tr("settings_shortcuts_primary"),
            tr("settings_shortcuts_alt"),
        ])
        table.setStyleSheet(STYLING_SETTINGS_TABLE)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        for row, (action, primary, alt) in enumerate(shortcuts):
            table.setItem(row, 0, QTableWidgetItem(action))
            table.setItem(row, 1, QTableWidgetItem(primary))
            table.setItem(row, 2, QTableWidgetItem(alt))

        layout.addWidget(table)
        return w

    def _build_ffmpeg_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        # Status
        available = _is_ffmpeg_available()
        status_text = tr("settings_ffmpeg_installed") if available else tr("settings_ffmpeg_not_installed")
        self._lbl_ffmpeg_status = QLabel(status_text)
        form.addRow(tr("settings_ffmpeg_status"), self._lbl_ffmpeg_status)

        # Version
        version = get_ffmpeg_version() if available else tr("settings_ffmpeg_unknown_version")
        self._lbl_ffmpeg_version = QLabel(version or tr("settings_ffmpeg_unknown_version"))
        form.addRow(tr("settings_ffmpeg_version"), self._lbl_ffmpeg_version)

        # Location
        try:
            loc = _ffmpeg_binary()
        except FFmpegNotFoundError:
            loc = "—"
        lbl_loc = QLabel(loc)
        lbl_loc.setWordWrap(True)
        lbl_loc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(tr("settings_ffmpeg_location"), lbl_loc)

        form.addRow(QLabel(""))  # spacer

        # Buttons
        btn_row = QHBoxLayout()
        if not available:
            self._btn_download = QPushButton(tr("settings_ffmpeg_btn_download"))
            qconnect(self._btn_download.clicked, self._on_download_ffmpeg)
            btn_row.addWidget(self._btn_download)
        else:
            self._btn_check = QPushButton(tr("settings_ffmpeg_btn_check_update"))
            qconnect(self._btn_check.clicked, self._on_check_update)
            btn_row.addWidget(self._btn_check)

        self._lbl_update_info = QLabel("")
        btn_row.addWidget(self._lbl_update_info, 1)
        form.addRow(btn_row)

        return w

    def _on_download_ffmpeg(self) -> None:
        if _sys.platform.startswith("win"):
            if install_ffmpeg_windows(self):
                self._lbl_ffmpeg_status.setText(tr("settings_ffmpeg_installed"))
                ver = get_ffmpeg_version()
                self._lbl_ffmpeg_version.setText(ver or tr("settings_ffmpeg_unknown_version"))

    def _on_check_update(self) -> None:
        self._btn_check.setEnabled(False)
        self._btn_check.setText(tr("settings_ffmpeg_checking"))
        self._lbl_update_info.setText("")

        def _bg():
            try:
                latest = check_ffmpeg_latest_version()
                current = get_ffmpeg_version()
                mw.taskman.run_on_main(lambda: self._on_check_result(current, latest))
            except Exception:
                traceback.print_exc()
                mw.taskman.run_on_main(lambda: self._on_check_result("", ""))

        threading.Thread(target=_bg, daemon=True).start()

    def _on_check_result(self, current: str, latest: str) -> None:
        self._btn_check.setEnabled(True)
        self._btn_check.setText(tr("settings_ffmpeg_btn_check_update"))

        if not latest:
            self._lbl_update_info.setText(tr("settings_ffmpeg_check_error"))
            return

        if current and latest and current.startswith(latest):
            self._lbl_update_info.setText(
                tr("settings_ffmpeg_up_to_date", version=current)
            )
        else:
            self._lbl_update_info.setText(
                tr("settings_ffmpeg_update_available",
                   current=current or "?", latest=latest)
            )
            # Add update button
            self._btn_update = QPushButton(
                tr("settings_ffmpeg_btn_update", version=latest)
            )
            qconnect(self._btn_update.clicked, self._on_update_ffmpeg)
            self._btn_check.parent().layout().addWidget(self._btn_update)

    def _on_update_ffmpeg(self) -> None:
        if _sys.platform.startswith("win"):
            if install_ffmpeg_windows(self):
                ver = get_ffmpeg_version()
                self._lbl_ffmpeg_version.setText(ver or tr("settings_ffmpeg_unknown_version"))
                self._lbl_update_info.setText(
                    tr("settings_ffmpeg_up_to_date", version=ver)
                )
                if hasattr(self, "_btn_update"):
                    self._btn_update.setVisible(False)

    def _on_save(self) -> None:
        cfg = _config()
        cfg["output_format"] = self._combo_format.currentText()
        cfg["output_bitrate"] = self._combo_bitrate.currentText()
        cfg["audio_field"] = self._input_audio_field.text().strip() or "Audio"
        _save_config(cfg)
        self.accept()
