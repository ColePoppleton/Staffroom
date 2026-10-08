"""A results table with per-row action buttons."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.panel import ActionTable
from staffroom.core.table import Table
from staffroom.shell.widgets.table_view import TableModel, TableWidget


class ActionTableWidget(QWidget):
    action_requested = Signal(str, object)  # action name, row dict

    def __init__(self, spec: ActionTable, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.model = TableModel()
        self.view = TableWidget(self.model)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.selectionModel().selectionChanged.connect(lambda *_: self._update_buttons())
        self.empty = QLabel("Nothing here yet.")
        self.empty.setProperty("role", "empty")
        self.empty.hide()
        self.caption = QLabel("")
        self.caption.setProperty("role", "faint")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.empty)
        layout.addWidget(self.view)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.buttons: dict[str, QPushButton] = {}
        for action in spec.actions:
            button = QPushButton(action.label)
            if action.help:
                button.setToolTip(action.help)
            if action.primary:
                button.setProperty("role", "primary")
            button.clicked.connect(lambda _c=False, name=action.name: self._fire(name))
            self.buttons[action.name] = button
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.caption)
        layout.addLayout(buttons)
        self._update_buttons()

    def set_table(self, table: Table) -> None:
        current = self.selected_row()
        self.model.set_table(table)
        for i, col in enumerate(table.columns):
            self.view.setColumnHidden(i, col in self.spec.hidden_columns)
        self.view.fit_columns()
        self.view.fit_rows(10)
        has_rows = len(table) > 0
        self.view.setVisible(has_rows)
        self.empty.setVisible(not has_rows)
        self.caption.setText(f"{len(table)} row{'s' if len(table) != 1 else ''}")
        if current is not None:
            self.select_matching(current)
        self._update_buttons()

    def selected_row(self) -> dict[str, Any] | None:
        rows = self.view.selectionModel().selectedRows()
        if not rows:
            return None
        return self.model.table().to_dicts()[rows[0].row()]

    def select_matching(self, row: dict[str, Any]) -> None:
        key = self.model.table().columns[-1] if self.model.table().columns else None
        if key is None:
            return
        for i, candidate in enumerate(self.model.table().to_dicts()):
            if candidate.get(key) == row.get(key):
                self.view.selectRow(i)
                return

    def select_first(self) -> None:
        if self.model.rowCount():
            self.view.selectRow(0)

    def _update_buttons(self) -> None:
        enabled = self.selected_row() is not None
        for button in self.buttons.values():
            button.setEnabled(enabled)

    def _fire(self, name: str) -> None:
        row = self.selected_row()
        if row is not None:
            self.action_requested.emit(name, row)
