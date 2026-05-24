# -*- coding: utf-8 -*-
"""
Audio Card Cutter — Anki Add-on (Pure Python / PyQt edition)
============================================================

Cut long audio files and create Anki cards with the cut segments.
UI built entirely with PyQt — no HTML/JS, no WebView.
"""

from typing import Optional
from aqt import mw
from aqt.qt import QAction, QKeySequence, QMenu, qconnect

from ._tr import init_i18n, tr
from .constants import ANKIVN_MENU_OBJECT_NAME, ANKIVN_MENU_TITLE
from .anki_interop import _config
from .ui import AudioCutterDialog

_dialog_instance: Optional[AudioCutterDialog] = None


def open_audio_cutter() -> None:
    global _dialog_instance  # noqa: PLW0603
    if _dialog_instance is None or not _dialog_instance.isVisible():
        _dialog_instance = AudioCutterDialog(mw)
    _dialog_instance.show()
    _dialog_instance.raise_()
    _dialog_instance.activateWindow()


def get_or_create_ankivn_menu() -> QMenu:
    menubar = mw.form.menubar
    for action in menubar.actions():
        menu = action.menu()
        if menu is None:
            continue
        if (
            menu.objectName() == ANKIVN_MENU_OBJECT_NAME
            or (action.text() or "").replace("&", "") == ANKIVN_MENU_TITLE
        ):
            return menu

    new_menu = QMenu(ANKIVN_MENU_TITLE, menubar)
    new_menu.setObjectName(ANKIVN_MENU_OBJECT_NAME)

    help_action = None
    for action in menubar.actions():
        if (action.text() or "").replace("&", "").lower() == "help":
            help_action = action
            break
    if help_action is not None:
        menubar.insertMenu(help_action, new_menu)
    else:
        menubar.addMenu(new_menu)
    return new_menu


def _setup() -> None:
    # Initialize i18n
    lang = (_config().get("language") or "").strip() or None
    init_i18n(lang)

    # Add menu entry
    action = QAction(tr("menu_item"), mw)
    action.setShortcut(QKeySequence("Ctrl+Shift+A"))
    qconnect(action.triggered, open_audio_cutter)
    get_or_create_ankivn_menu().addAction(action)


_setup()
