"""A small dialog so plugins can ``ctx.resources.pick()`` a library file."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QListWidget,
    QVBoxLayout,
    QWidget,
)

from teaching_tools.core.library.service import LibraryService


class ResourcePickerDialog(QDialog):
    def __init__(
        self, service: LibraryService, filter_ext: str | None, parent: QWidget | None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pick a resource")
        self.resize(560, 480)
        self.service = service
        self.filter_ext = filter_ext.lower() if filter_ext else None
        layout = QVBoxLayout(self)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter…")
        self.search.textChanged.connect(self.refresh)
        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        standard = QDialogButtonBox.StandardButton
        buttons = QDialogButtonBox(standard.Ok | standard.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(self.search)
        layout.addWidget(self.list, 1)
        layout.addWidget(buttons)
        self.refresh("")

    def refresh(self, text: str) -> None:
        self.list.clear()
        needle = text.lower()
        for res in self.service.resources():
            if res.cloud_only:
                continue
            if self.filter_ext and res.ext != self.filter_ext:
                continue
            if needle and needle not in res.rel_path.lower():
                continue
            self.list.addItem(res.rel_path)
        if self.list.count():
            self.list.setCurrentRow(0)

    def chosen(self) -> Path | None:
        item = self.list.currentItem()
        return self.service.absolute(item.text()) if item else None


def pick_resource(
    service: LibraryService, filter_ext: str | None, parent: QWidget | None
) -> Path | None:
    dialog = ResourcePickerDialog(service, filter_ext, parent)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.chosen()
    return None
