"""A command to paste into Terminal, shown in monospace with a *Copy* button."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

COPIED_FOR_MS = 1500


class CommandBox(QFrame):
    """One line of shell, selectable, with a button that puts it on the
    clipboard and says *Copied* for a moment."""

    def __init__(self, command: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("CommandBox")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 8, 8)
        row.setSpacing(10)
        self.text = QLabel(command)
        self.text.setObjectName("CommandText")
        self.text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text.setWordWrap(True)
        self.copy_button = QPushButton("Copy")
        self.copy_button.setToolTip("Copy the command to the clipboard")
        self.copy_button.clicked.connect(self.copy)
        row.addWidget(self.text, 1)
        row.addWidget(self.copy_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def command(self) -> str:
        return self.text.text()

    def set_command(self, command: str) -> None:
        self.text.setText(command)

    def copy(self) -> None:
        QApplication.clipboard().setText(self.command())
        self.copy_button.setText("Copied")
        # The button is the context: no reset fires after the box is gone.
        button = self.copy_button
        QTimer.singleShot(COPIED_FOR_MS, button, lambda: button.setText("Copy"))
