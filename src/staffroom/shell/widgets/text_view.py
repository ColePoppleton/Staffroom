"""Read-only text block, monospace by default (diffs, reports)."""

from __future__ import annotations

from PySide6.QtWidgets import QPlainTextEdit, QWidget

from staffroom.core.panel import TextView


class TextViewWidget(QPlainTextEdit):
    def __init__(self, spec: TextView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setObjectName("CodeView" if spec.monospace else "TextView")
        self.setReadOnly(True)
        wrap = QPlainTextEdit.LineWrapMode
        self.setLineWrapMode(wrap.NoWrap if spec.monospace else wrap.WidgetWidth)
        self.setMinimumHeight(220)
        self.setPlaceholderText("Nothing to show yet.")

    def set_text(self, text: str) -> None:
        self.setPlainText(text)
