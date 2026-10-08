"""Layout primitives: a titled card and a hairline divider."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


def make_label(text: str, role: str = "", *, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    label.setWordWrap(wrap)
    return label


class Divider(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("Divider")
        self.setFrameShape(QFrame.Shape.NoFrame)


class Card(QFrame):
    """A surface with an optional title row and a vertical body layout."""

    def __init__(self, title: str = "", help_text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 18)
        outer.setSpacing(12)

        if title or help_text:
            head = QHBoxLayout()
            head.setSpacing(10)
            if title:
                self.title_label = make_label(title, "section")
                head.addWidget(self.title_label)
            head.addStretch(1)
            self.trailing = QHBoxLayout()
            self.trailing.setSpacing(8)
            head.addLayout(self.trailing)
            outer.addLayout(head)
            if help_text:
                outer.addWidget(make_label(help_text, "muted", wrap=True))

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        outer.addLayout(self.body)

    def add(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def add_trailing(self, widget: QWidget) -> QWidget:
        self.trailing.addWidget(widget)
        return widget
