"""Layout primitives: a titled card and a hairline divider."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

WORD_JOINER = "\u2060"  # invisible; forbids a line break where it stands


class SentenceLabel(QLabel):
    """A wrapping sentence that may name a folder under home: Qt breaks a line
    after a slash, so "~/TeachingSessions" could end one line with "~/" and
    start the next with "TeachingSessions" (#23). A word joiner after each
    ``~/`` keeps the path whole. :meth:`text` gives the sentence back without
    it, so whatever reads or rewrites the text (tests, screenshot mode) sees
    plain words."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 (Qt's name)
        super().setText(text.replace(WORD_JOINER, "").replace("~/", "~/" + WORD_JOINER))

    def text(self) -> str:
        return super().text().replace(WORD_JOINER, "")


def make_label(text: str, role: str = "", *, wrap: bool = False) -> QLabel:
    label = SentenceLabel(text) if wrap else QLabel(text)
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
