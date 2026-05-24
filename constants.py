# -*- coding: utf-8 -*-
"""
Constants and styling configurations for Audio Card Cutter.
"""

# Audio and FFmpeg download settings
FFMPEG_DOWNLOAD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
CHUNK_SIZE = 64 * 1024  # 64 KB chunk size for downloads

# Time values and steps (magic numbers refactored to constants)
PREVIEW_DURATION_SEC = 1.5
REACTION_OFFSET_SEC = 0.2
SEEK_STEP_LARGE_SEC = 5.0
SEEK_STEP_SMALL_SEC = 1.0
NUDGE_STEP_LARGE_SEC = 0.5
NUDGE_STEP_SMALL_SEC = 0.1
TICK_INTERVAL_MS = 50

# Menu settings
ANKIVN_MENU_OBJECT_NAME = "sf_ankivn_menu"
ANKIVN_MENU_TITLE = "AnkiVN"

# Audio extensions
AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".ogg", ".flac",
    ".aac", ".opus", ".wma", ".mp4", ".mkv",
    ".webm", ".3gp"
}

# UI Stylesheets (magic strings refactored to constants)
STYLING_LBL_FILE_LOADED = "color: #ddd;"
STYLING_LBL_FILE_UNLOADED = "color: #888;"
STYLING_FFMPEG_STATUS = "padding: 4px 8px; background: #5a2a2a; color: #ffd2d2; border-radius: 4px;"
STYLING_PLAY_BUTTON = "padding: 2px 4px;"
STYLING_NUDGE_BUTTON = "padding: 2px 0px; min-width: 44px; max-width: 50px;"
STYLING_LBL_TIME = "font-family: Consolas, 'Courier New', monospace;"
STYLING_QUEUE_LIST = "font-family: Consolas, 'Courier New', monospace; font-size: 11px;"
STYLING_QUEUE_CUT_ALL = "font-weight: 600;"
STYLING_DECK_BUTTON = "text-align: left; padding: 4px 8px;"
STYLING_NOTETYPE_BUTTON = "text-align: left; padding: 4px 8px;"
STYLING_ACTIVE_FIELD = "QPlainTextEdit { border: 1.5px solid #5b8def; }"
STYLING_ACTIVE_LABEL = "color: #5b8def; font-weight: bold;"
STYLING_LINE_EDIT_FOCUS = "QLineEdit:focus { border: 1.5px solid #2196F3; }"
STYLING_SEARCH_DIALOG = "QListWidget::item:hover { background-color: #2a2a2a; }"
STYLING_BTN_CUT = "QPushButton { padding: 6px 10px; }"
STYLING_BTN_ADD_NOTE = "QPushButton { padding: 6px 10px; }"
STYLING_BTN_CUT_AND_ADD = "QPushButton { padding: 6px 12px; font-weight: 600; }"
STYLING_COMBO_SPEED_STYLING = "padding: 2px;"

# Waveform extraction and rendering settings
WAVEFORM_SAMPLE_RATE = 100  # Extract 100 samples per second
WAVEFORM_BAR_WIDTH = 2
WAVEFORM_BAR_SPACING = 1

# Dialog CRUD button styling
STYLING_DIALOG_CRUD_BTN = "padding: 4px 10px; min-width: 60px;"
STYLING_DIALOG_CRUD_DELETE = "padding: 4px 10px; min-width: 60px; color: #ff6b6b;"
STYLING_SETTINGS_TAB = "QTabBar::tab { padding: 6px 16px; }"
STYLING_SETTINGS_TABLE = (
    "QTableWidget { font-size: 12px; }"
    "QTableWidget::item { padding: 4px 8px; }"
    "QHeaderView::section { padding: 4px 8px; font-weight: 600; }"
)
STYLING_QUEUE_PLAY_BTN = "padding: 2px 6px; min-width: 50px;"
STYLING_SETTINGS_BTN = "padding: 4px 8px; font-size: 14px; min-width: 28px;"

