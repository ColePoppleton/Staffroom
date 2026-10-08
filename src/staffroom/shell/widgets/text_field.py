"""A single short line of text."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QWidget

from staffroom.core.panel import TextField


class TextFieldWidget(QWidget):
    def __init__(self, spec: TextField, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(spec.placeholder)
        self.edit.setMaxLength(spec.max_length)
        self.edit.setClearButtonEnabled(True)
        self.counter = QLabel("")
        self.counter.setProperty("role", "faint")
        self.edit.textChanged.connect(self._update_counter)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.counter)
        self._update_counter("")

    def _update_counter(self, text: str) -> None:
        self.counter.setText(f"{len(text)}/{self.spec.max_length}")

    def value(self) -> str:
        return self.edit.text().strip()

    def set_value(self, text: str) -> None:
        self.edit.setText(text)
