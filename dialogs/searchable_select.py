# -*- coding: utf-8 -*-
"""
SearchableSelectDialog base class for selector dialogs.
"""
from typing import Optional
from aqt.qt import (
    QDialog, QHBoxLayout, QLineEdit, QListWidget, QVBoxLayout, QWidget, Qt, qconnect
)
from .._tr import tr
from ..constants import STYLING_LINE_EDIT_FOCUS, STYLING_SEARCH_DIALOG


class SearchableSelectDialog(QDialog):
    """Modal dialog with a search box, filterable list, and optional CRUD buttons."""

    def __init__(self, title: str, items: list[str],
                 current: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(400, 460)
        self._items = items
        self._result: Optional[str] = None

        layout = QVBoxLayout(self)
        self._search = QLineEdit()
        self._search.setPlaceholderText(tr("search_placeholder"))
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet(STYLING_LINE_EDIT_FOCUS)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.addItems(items)
        self._list.setStyleSheet(STYLING_SEARCH_DIALOG)
        layout.addWidget(self._list, 1)

        # CRUD buttons row (subclasses populate this)
        self._crud_row = QHBoxLayout()
        self._crud_row.setContentsMargins(0, 4, 0, 0)
        self._build_crud_buttons(self._crud_row)
        layout.addLayout(self._crud_row)

        # Pre-select current item
        if current:
            matches = self._list.findItems(
                current, Qt.MatchFlag.MatchExactly
            )
            if matches:
                self._list.setCurrentItem(matches[0])
                self._list.scrollToItem(matches[0])

        qconnect(self._search.textChanged, self._on_filter)
        qconnect(self._list.itemDoubleClicked, self._on_accept)
        qconnect(self._search.returnPressed, self._on_enter)

    def _build_crud_buttons(self, layout: QHBoxLayout) -> None:
        """Override in subclasses to add Add/Rename/Delete buttons."""
        pass

    def _on_filter(self, text: str) -> None:
        needle = text.lower()
        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(needle not in item.text().lower())

    def _on_accept(self, item) -> None:
        self._result = item.text()
        self.accept()

    def _on_enter(self) -> None:
        current = self._list.currentItem()
        if current and not current.isHidden():
            self._result = current.text()
            self.accept()
            return
        # Pick first visible item
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not item.isHidden():
                self._result = item.text()
                self.accept()
                return

    def _refresh_list(self, items: list[str], select: str = "") -> None:
        """Rebuild list contents and optionally select an item."""
        self._items = items
        self._list.clear()
        self._list.addItems(items)
        self._search.clear()
        if select:
            matches = self._list.findItems(select, Qt.MatchFlag.MatchExactly)
            if matches:
                self._list.setCurrentItem(matches[0])

    @staticmethod
    def select(title: str, items: list[str], current: str = "",
               parent: Optional[QWidget] = None) -> Optional[str]:
        dlg = SearchableSelectDialog(title, items, current, parent)
        if dlg.exec() and dlg._result:
            return dlg._result
        return None
