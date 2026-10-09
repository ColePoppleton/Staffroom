"""A segmented switch for a :class:`~staffroom.core.panel.Choice`: two or
three exclusive buttons in one rounded frame."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QWidget

from staffroom.core.panel import Choice


class ChoiceWidget(QFrame):
    changed = Signal(str)

    def __init__(self, spec: Choice, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setObjectName("Segmented")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for value, text in spec.choices:
            button = QPushButton(text)
            button.setObjectName("Segment")
            button.setCheckable(True)
            button.setToolTip(spec.help or text)
            self.group.addButton(button)
            self.buttons[value] = button
            layout.addWidget(button)
            button.toggled.connect(lambda on, v=value: self._toggled(on, v))
        self.set_value(spec.initial)

    def _toggled(self, on: bool, value: str) -> None:
        if on:
            self.changed.emit(value)

    def value(self) -> str:
        for value, button in self.buttons.items():
            if button.isChecked():
                return value
        return self.spec.initial

    def set_value(self, value: str) -> None:
        button = self.buttons.get(value)
        if button is not None:
            button.setChecked(True)
