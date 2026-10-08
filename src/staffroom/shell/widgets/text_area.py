"""Several lines of free text, monospace by default (pasted code)."""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from staffroom.core.panel import TextArea


class TextAreaWidget(QPlainTextEdit):
    def __init__(self, spec: TextArea, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setObjectName("CodeView" if spec.monospace else "TextView")
        if spec.monospace:
            self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
            self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setPlaceholderText(spec.placeholder)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self.setFixedHeight(18 * spec.rows + 16)

    def value(self) -> str:
        return self.toPlainText()

    def set_value(self, text: str) -> None:
        self.setPlainText(text)
