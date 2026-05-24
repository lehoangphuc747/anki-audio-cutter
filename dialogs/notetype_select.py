# -*- coding: utf-8 -*-
"""
NoteTypeSelectDialog with CRUD operations for Anki note types.
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


class NoteTypeSelectDialog(SearchableSelectDialog):
    """Note type selector with CRUD operations."""

    def _build_crud_buttons(self, layout: QHBoxLayout) -> None:
        self.btn_add = QPushButton(tr("notetype_btn_add"))
        self.btn_add.setStyleSheet(STYLING_DIALOG_CRUD_BTN)
        self.btn_rename = QPushButton(tr("notetype_btn_rename"))
        self.btn_rename.setStyleSheet(STYLING_DIALOG_CRUD_BTN)
        self.btn_delete = QPushButton(tr("notetype_btn_delete"))
        self.btn_delete.setStyleSheet(STYLING_DIALOG_CRUD_DELETE)
        layout.addStretch(1)
        layout.addWidget(self.btn_add)
        layout.addWidget(self.btn_rename)
        layout.addWidget(self.btn_delete)

        qconnect(self.btn_add.clicked, self._on_add_notetype)
        qconnect(self.btn_rename.clicked, self._on_rename_notetype)
        qconnect(self.btn_delete.clicked, self._on_delete_notetype)

    def _on_add_notetype(self) -> None:
        col = mw.col
        if col is None:
            return
        all_nt = [n.name for n in col.models.all_names_and_ids()]

        dlg = QDialog(self)
        dlg.setWindowTitle(tr("notetype_add_title"))
        dlg.setMinimumWidth(350)
        form = QFormLayout(dlg)

        combo_clone = QComboBox()
        combo_clone.addItems(all_nt)
        form.addRow(tr("notetype_add_clone_label"), combo_clone)

        input_name = QLineEdit()
        input_name.setPlaceholderText(tr("notetype_add_name_label"))
        form.addRow(tr("notetype_add_name_label"), input_name)

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
                tooltip(tr("notetype_add_empty_name"), parent=self)
                return
            clone_from = combo_clone.currentText()
            src_model = col.models.by_name(clone_from)
            if src_model:
                new_model = col.models.copy(src_model)
                new_model["name"] = name
                col.models.add(new_model)
                new_nts = [n.name for n in col.models.all_names_and_ids()]
                self._refresh_list(new_nts, name)

    def _on_rename_notetype(self) -> None:
        col = mw.col
        if col is None:
            return
        current = self._list.currentItem()
        if not current:
            tooltip(tr("notetype_select_first"), parent=self)
            return
        old_name = current.text()
        new_name, ok = QInputDialog.getText(
            self, tr("notetype_rename_title"),
            tr("notetype_rename_label", name=old_name),
            text=old_name,
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            model = col.models.by_name(old_name)
            if model:
                model["name"] = new_name.strip()
                col.models.save(model)
                new_nts = [n.name for n in col.models.all_names_and_ids()]
                self._refresh_list(new_nts, new_name.strip())

    def _on_delete_notetype(self) -> None:
        col = mw.col
        if col is None:
            return
        current = self._list.currentItem()
        if not current:
            tooltip(tr("notetype_select_first"), parent=self)
            return
        name = current.text()
        model = col.models.by_name(name)
        if not model:
            return
        # Count notes using this note type
        note_count = col.models.use_count(model)
        if note_count > 0:
            ans = QMessageBox.question(
                self, tr("notetype_delete_title"),
                tr("notetype_delete_confirm", name=name, count=note_count),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
        else:
            ans = QMessageBox.question(
                self, tr("notetype_delete_title"),
                tr("notetype_delete_confirm", name=name, count=0),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
        col.models.remove(model)
        new_nts = [n.name for n in col.models.all_names_and_ids()]
        self._refresh_list(new_nts)
        tooltip(tr("notetype_delete_success"), parent=self)

    @staticmethod
    def select(title: str, items: list[str], current: str = "",
               parent: Optional[QWidget] = None) -> Optional[str]:
        dlg = NoteTypeSelectDialog(title, items, current, parent)
        if dlg.exec() and dlg._result:
            return dlg._result
        return None
