"""One labelled group in the workbench: a small capitalised heading, the
widget, and help text under it. The inputs pane separates groups with
hairlines; nothing is boxed in a card."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QVBoxLayout, QWidget

from staffroom.shell.widgets.card import make_label


def eyebrow(text: str) -> QLabel:
    """A group heading: small, capitalised, letter-spaced (role ``eyebrow``)."""
    label = make_label(text.upper(), "eyebrow")
    label.setToolTip(text)
    return label


class InputGroup(QWidget):
    """A heading row (with room on the right for a trailing link), a body,
    and optional help text under the body.

    A ``joined`` group continues the one above it (``PanelSpec.joined``): it
    sits close under it, with no hairline, and its heading is a small plain
    label rather than an eyebrow.

    :meth:`set_flag` marks the group as the input to fix after a failed run
    (``ToolError.input_key``, #21): its boxes take the danger border and the
    hint, if any, replaces the help text until :meth:`clear_flag`."""

    def __init__(
        self,
        title: str = "",
        help_text: str = "",
        parent: QWidget | None = None,
        *,
        joined: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("InputGroup")
        self.title = title
        self.joined = joined
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0 if joined else 12, 0, 14)
        outer.setSpacing(6 if joined else 8)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.title_label = make_label(title, "muted") if joined else eyebrow(title)
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

        self.help_text = help_text
        self.help_label = make_label(help_text, "faint", wrap=True)
        self.help_label.setVisible(bool(help_text))
        outer.addWidget(self.help_label)
        self.flagged = False
        self._widgets: list[QWidget] = []

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.body.addWidget(widget, stretch)
        self._widgets.append(widget)
        return widget

    def set_flag(self, hint: str = "") -> None:
        """Mark this input as the one to fix; ``hint`` shows in place of the help."""
        self._mark(True)
        text = hint or self.help_text
        self.help_label.setText(text)
        self.help_label.setProperty("role", "flag" if hint else "faint")
        _repolish(self.help_label)
        self.help_label.setVisible(bool(text))

    def clear_flag(self) -> None:
        if not self.flagged:
            return
        self._mark(False)
        self.help_label.setText(self.help_text)
        self.help_label.setProperty("role", "faint")
        _repolish(self.help_label)
        self.help_label.setVisible(bool(self.help_text))

    def _mark(self, flagged: bool) -> None:
        self.flagged = flagged
        for widget in self._boxes():
            widget.setProperty("flagged", flagged)
            _repolish(widget)

    def _boxes(self) -> list[QWidget]:
        """The text boxes in the group: what the danger border goes on."""
        boxes: list[QWidget] = []
        for widget in self._widgets:
            if isinstance(widget, QLineEdit | QPlainTextEdit):
                boxes.append(widget)
            boxes.extend(widget.findChildren(QLineEdit))
            boxes.extend(widget.findChildren(QPlainTextEdit))
        return boxes

    def add_trailing(self, widget: QWidget) -> QWidget:
        self.trailing.addWidget(widget)
        return widget


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
