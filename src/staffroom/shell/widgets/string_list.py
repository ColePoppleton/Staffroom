"""A small editable list of strings: a list view, a line edit and Add / Remove
buttons. Used for the library's exclusion list; any setting that is a list of
short values can use it."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class StringListEditor(QWidget):
    """``changed`` fires with the full ``list[str]`` after every add or remove.
    Values are stripped; blanks and duplicates are ignored."""

    changed = Signal(object)

    def __init__(self, placeholder: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.list = QListWidget()
        self.list.setObjectName("StringList")
        self.list.setAlternatingRowColors(False)
        self.list.setMaximumHeight(120)
        self.list.itemSelectionChanged.connect(self._sync_buttons)
        layout.addWidget(self.list)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        self.edit.setClearButtonEnabled(True)
        self.edit.returnPressed.connect(self.add_current)
        self.edit.textChanged.connect(self._sync_buttons)
        self.add_button = QPushButton("Add")
        self.add_button.setProperty("role", "ghost")
        self.add_button.clicked.connect(self.add_current)
        self.remove_button = QPushButton("Remove")
        self.remove_button.setProperty("role", "ghost")
        self.remove_button.clicked.connect(self.remove_selected)
        row.addWidget(self.edit, 1)
        row.addWidget(self.add_button)
        row.addWidget(self.remove_button)
        layout.addLayout(row)
        self._sync_buttons()

    # -- value -----------------------------------------------------------
    def values(self) -> list[str]:
        # Rows are plain strings (addItem(str) makes no wrapper); the item(i) wrappers
        # here are dropped with the comprehension, before any clear or takeItem (#54).
        return [self.list.item(i).text() for i in range(self.list.count())]

    def set_values(self, values: Iterable[str]) -> None:
        """Replace the contents without emitting ``changed``."""
        self.list.clear()
        for v in values:
            v = v.strip()
            if v and v not in self.values():
                self.list.addItem(v)
        self._sync_buttons()

    # -- edits -----------------------------------------------------------
    def add(self, value: str) -> bool:
        value = value.strip()
        if not value or value in self.values():
            return False
        self.list.addItem(value)
        self.changed.emit(self.values())
        return True

    def add_current(self) -> None:
        if self.add(self.edit.text()):
            self.edit.clear()
        self.edit.setFocus()

    def remove(self, value: str) -> bool:
        for i in range(self.list.count()):
            if self.list.item(i).text() == value:  # transient wrapper, gone before takeItem
                self.list.takeItem(i)  # the row comes back to Python and is dropped at once
                self.changed.emit(self.values())
                return True
        return False

    def remove_selected(self) -> None:
        rows = sorted({i.row() for i in self.list.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for r in rows:
            self.list.takeItem(r)
        self.changed.emit(self.values())
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        self.add_button.setEnabled(bool(self.edit.text().strip()))
        self.remove_button.setEnabled(bool(self.list.selectedIndexes()))
