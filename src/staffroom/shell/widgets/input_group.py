"""One labelled group in the workbench: a small capitalised heading, the
widget, and help text under it. The inputs pane separates groups with
hairlines; nothing is boxed in a card."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from staffroom.shell.widgets.card import make_label


def eyebrow(text: str) -> QLabel:
    """A group heading: small, capitalised, letter-spaced (role ``eyebrow``)."""
    label = make_label(text.upper(), "eyebrow")
    label.setToolTip(text)
    return label


class InputGroup(QWidget):
    """A heading row (with room on the right for a trailing link), a body,
    and optional help text under the body."""

    def __init__(self, title: str = "", help_text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("InputGroup")
        self.title = title
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 12, 0, 14)
        outer.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.title_label = eyebrow(title)
        self.title_label.setVisible(bool(title))
        head.addWidget(self.title_label)
        head.addStretch(1)
        self.trailing = QHBoxLayout()
        self.trailing.setSpacing(6)
        head.addLayout(self.trailing)
        outer.addLayout(head)

        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        outer.addLayout(self.body)

        self.help_label = make_label(help_text, "faint", wrap=True)
        self.help_label.setVisible(bool(help_text))
        outer.addWidget(self.help_label)

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.body.addWidget(widget, stretch)
        return widget

    def add_trailing(self, widget: QWidget) -> QWidget:
        self.trailing.addWidget(widget)
        return widget
