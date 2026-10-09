"""A label that never grows past a few lines: longer text is cut with an
ellipsis (at the end, or in the middle for paths) and shown in full in the
tooltip. ``text()`` still returns the whole string, so callers (and tests)
read what was set, not what fits."""

from __future__ import annotations

from itertools import pairwise

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QResizeEvent, QTextLayout, QTextOption
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class ElidedLabel(QLabel):
    def __init__(
        self,
        text: str = "",
        parent: QWidget | None = None,
        *,
        max_lines: int = 1,
        mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
        auto_tooltip: bool = True,
    ) -> None:
        super().__init__(parent)
        self.max_lines = max(1, max_lines)
        self.mode = mode
        self.auto_tooltip = auto_tooltip  # False: the caller sets its own tooltip
        self._full = ""
        self.setWordWrap(False)  # lines are broken by _elide, exactly
        # Never widens its layout: the text fits the width it is given.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def text(self) -> str:
        return self._full

    def setText(self, text: str) -> None:  # noqa: N802
        self._full = text
        self._fit()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(40, super().minimumSizeHint().height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self._fit()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._fit()

    def _fit(self) -> None:
        shown = self._elide(self._full, max(self.contentsRect().width(), 40))
        super().setText(shown)
        if self.auto_tooltip:
            self.setToolTip(self._full if shown.replace("\n", " ") != self._full else "")
        self.setMaximumHeight(self.fontMetrics().lineSpacing() * self.max_lines + 6)

    def _elide(self, text: str, width: int) -> str:
        """The text broken into at most ``max_lines`` lines of ``width``, the
        last one elided. Lines are laid out here (breaking a long path
        anywhere if it must) rather than by QLabel, so the count is exact."""
        metrics = self.fontMetrics()
        if self.max_lines == 1 or not text:
            return metrics.elidedText(text, self.mode, width)
        layout = QTextLayout(text, self.font())
        option = QTextOption()
        option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        layout.setTextOption(option)
        starts: list[int] = []
        layout.beginLayout()
        while True:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(width)
            starts.append(line.textStart())
        layout.endLayout()
        starts.append(len(text))
        lines = [text[a:b].strip() for a, b in pairwise(starts)]
        if len(lines) <= self.max_lines:
            return "\n".join(lines)
        rest = text[starts[self.max_lines - 1] :].strip()
        last = metrics.elidedText(rest, self.mode, width)
        return "\n".join([*lines[: self.max_lines - 1], last])
