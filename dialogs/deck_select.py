# -*- coding: utf-8 -*-
"""
DeckSelectDialog with CRUD operations for deck selection.
"""
from typing import Optional
from aqt import mw
from aqt.qt import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QInputDialog, QLineEdit,
    QMessageBox, QPushButton, QWidget, qconnect
)
from aqt.utils import tooltip

from .searchable_select import SearchableSelectDialog
from .._tr import tr
from ..constants import STYLING_DIALOG_CRUD_BTN, STYLING_DIALOG_CRUD_DELETE


class DeckSelectDialog(SearchableSelectDialog):
    """Deck selector with CRUD operations and subdeck support."""

    def _build_crud_buttons(self, layout: QHBoxLayout) -> None:
        self.btn_add = QPushButton(tr("deck_btn_add"))
        self.btn_add.setStyleSheet(STYLING_DIALOG_CRUD_BTN)
        self.btn_rename = QPushButton(tr("deck_btn_rename"))
        self.btn_rename.setStyleSheet(STYLING_DIALOG_CRUD_BTN)
        self.btn_delete = QPushButton(tr("deck_btn_delete"))
        self.btn_delete.setStyleSheet(STYLING_DIALOG_CRUD_DELETE)
        layout.addStretch(1)
        layout.addWidget(self.btn_add)
        layout.addWidget(self.btn_rename)
        layout.addWidget(self.btn_delete)

        qconnect(self.btn_add.clicked, self._on_add_deck)
        qconnect(self.btn_rename.clicked, self._on_rename_deck)
        qconnect(self.btn_delete.clicked, self._on_delete_deck)

    def _on_add_deck(self) -> None:
        col = mw.col
        if col is None:
            return
        # Build parent deck choices
        all_decks = [d.name for d in col.decks.all_names_and_ids()]
        parents = [tr("deck_add_parent_top")] + sorted(all_decks)

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("deck_add_title"))
        dlg.setMinimumWidth(350)
        form = QFormLayout(dlg)

        combo_parent = QComboBox()
        combo_parent.addItems(parents)
        form.addRow(tr("deck_add_parent_label"), combo_parent)

        input_name = QLineEdit()
        input_name.setPlaceholderText(tr("deck_add_name_label"))
        form.addRow(tr("deck_add_name_label"), input_name)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_cancel = QPushButton(tr("ffmpeg_cancel"))
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        form.addRow(btn_row)

        qconnect(btn_ok.clicked, dlg.accept)
        qconnect(btn_cancel.clicked, dlg.reject)

        if dlg.exec():
            name = input_name.text().strip()
            if not name:
                tooltip(tr("deck_add_empty_name"), parent=self)
                return
            parent_sel = combo_parent.currentText()
            if parent_sel == tr("deck_add_parent_top"):
                full_name = name
            else:
                full_name = f"{parent_sel}::{name}"
            col.decks.id(full_name)  # Creates if not exists
            # Refresh list
            new_decks = [d.name for d in col.decks.all_names_and_ids()]
            self._refresh_list(new_decks, full_name)

    def _on_rename_deck(self) -> None:
        col = mw.col
        if col is None:
            return
        current = self._list.currentItem()
        if not current:
            tooltip(tr("deck_select_first"), parent=self)
            return
        old_name = current.text()
        new_name, ok = QInputDialog.getText(
            self, tr("deck_rename_title"),
            tr("deck_rename_label", name=old_name),
            text=old_name,
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            did = col.decks.id_for_name(old_name)
            if did:
                deck = col.decks.get(did)
                deck["name"] = new_name.strip()
                col.decks.save(deck)
                new_decks = [d.name for d in col.decks.all_names_and_ids()]
                self._refresh_list(new_decks, new_name.strip())

    def _on_delete_deck(self) -> None:
        col = mw.col
        if col is None:
            return
        current = self._list.currentItem()
        if not current:
            tooltip(tr("deck_select_first"), parent=self)
            return
        name = current.text()
        ans = QMessageBox.question(
            self, tr("deck_delete_title"),
            tr("deck_delete_confirm", name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ans == QMessageBox.StandardButton.Yes:
            did = col.decks.id_for_name(name)
            if did:
                col.decks.remove([did])
                new_decks = [d.name for d in col.decks.all_names_and_ids()]
                self._refresh_list(new_decks)
                tooltip(tr("deck_delete_success"), parent=self)

    @staticmethod
    def select(title: str, items: list[str], current: str = "",
               parent: Optional[QWidget] = None) -> Optional[str]:
        dlg = DeckSelectDialog(title, items, current, parent)
        if dlg.exec() and dlg._result:
            return dlg._result
        return None
