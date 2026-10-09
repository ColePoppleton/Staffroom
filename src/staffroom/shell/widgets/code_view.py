"""A read-only code view with line numbers: the program a code tool works on,
or a translation it made.

Line numbers sit in a gutter on the left, counted the way the printed sheets
count them (:func:`staffroom.core.codeinput.numbered_listing`: line 1 is the
file's first line). Python is coloured with the Library preview's
:class:`~staffroom.shell.library.highlighter.PythonHighlighter`.

Lines can be *lit* (:meth:`CodeViewWidget.highlight_lines`): a soft band across
the line and a mark in the gutter, e.g. the line a trace table row points at.
Clicking a line emits :attr:`CodeViewWidget.line_clicked` with its number.

It is not an editor. Read-only by default; a panel may make it editable for
pasting (``setReadOnly(False)``), and that is all: no save, no run.

All colours come from the stylesheet (``qproperty-gutterColor`` …), so a theme
change repaints."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from staffroom.shell.library.highlighter import CodeColors, PythonHighlighter
from staffroom.shell.widgets.paint import color_property, default_colors

GUTTER_PAD = 10  # space either side of the numbers
MARK_WIDTH = 3  # the lit line's bar at the gutter's left edge
CODE_COLORS = ("keyword", "builtin", "name", "number", "string", "comment")


class _Gutter(QWidget):
    """The line numbers. Painted by the view; a click selects a line."""

    def __init__(self, view: CodeViewWidget) -> None:
        super().__init__(view)
        self.view = view
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.view.gutter_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        self.view.paint_gutter(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        line = self.view.line_at(int(event.position().y()))
        if line is not None:
            self.view.line_clicked.emit(line)


class CodeViewWidget(QPlainTextEdit):
    """Monospace, unwrapped, numbered and (for Python) highlighted."""

    line_clicked = Signal(int)  # 1-based line number

    gutterColor = color_property("gutter")  # noqa: N815 - Qt property names
    markColor = color_property("mark")  # noqa: N815
    lineColor = color_property("line")  # noqa: N815
    keywordColor = color_property("keyword")  # noqa: N815
    builtinColor = color_property("builtin")  # noqa: N815
    nameColor = color_property("name")  # noqa: N815
    numberColor = color_property("number")  # noqa: N815
    stringColor = color_property("string")  # noqa: N815
    commentColor = color_property("comment")  # noqa: N815

    def __init__(
        self, parent: QWidget | None = None, *, highlight: bool = True, read_only: bool = True
    ) -> None:
        super().__init__(parent)
        self._colors = default_colors("gutter", "mark", "line", *CODE_COLORS)
        self.setObjectName("CodeView")
        # Matched by the stylesheet's lit-line rule (always set: the colours
        # must be there before the first line is lit).
        self.setProperty("lit", True)
        self.setReadOnly(read_only)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))
        self._lit: list[int] = []
        self._fit: tuple[int, int] | None = None
        self._gutter = _Gutter(self)
        self.highlighter: PythonHighlighter | None = None
        if highlight:
            self.highlighter = PythonHighlighter(self.document(), self._code_colors())
        # The six code colours arrive one property at a time when the
        # stylesheet is applied: re-colour once, after the last.
        self._recolour = QTimer(self)
        self._recolour.setSingleShot(True)
        self._recolour.setInterval(0)
        self._recolour.timeout.connect(self._apply_code_colors)
        self.blockCountChanged.connect(self._update_margins)
        self.updateRequest.connect(self._scroll_gutter)
        self._update_margins()

    # -- colours ---------------------------------------------------------
    def _code_colors(self) -> CodeColors:
        c = self._colors
        return CodeColors(*(c[name].name() for name in CODE_COLORS))

    def _apply_code_colors(self) -> None:
        if self.highlighter is not None:
            self.highlighter.set_colors(self._code_colors())
        self._paint_lit()

    def update(self) -> None:  # type: ignore[override]
        """A colour property changed (``paint.color_property`` calls this):
        repaint, and re-colour the code once the stylesheet is done."""
        self.viewport().update()
        if hasattr(self, "_recolour"):  # properties can arrive mid-construction
            self._gutter.update()
            self._recolour.start()

    # -- text ------------------------------------------------------------
    def set_text(self, text: str) -> None:
        """Show ``text``; a trailing newline adds no empty numbered line."""
        self._lit = []
        self.setPlainText(text.rstrip("\n"))
        self._paint_lit()

    def line_count(self) -> int:
        return self.blockCount() if self.toPlainText() else 0

    def fit_height(self, min_lines: int, max_lines: int) -> None:
        """As tall as its lines (within limits), and the sideways scroll bar
        when a line is too long for the width; it scrolls past ``max_lines``.
        Refitted when the width changes."""
        self._fit = (min_lines, max_lines)
        lines = max(min_lines, min(max_lines, max(self.blockCount(), 1)))
        frame = self.frameWidth() * 2 + int(self.document().documentMargin() * 2) + 8
        height = lines * self.fontMetrics().lineSpacing() + frame
        if self._too_wide():
            height += self.horizontalScrollBar().sizeHint().height()
        self.setFixedHeight(height)

    def _too_wide(self) -> bool:
        widest = max(
            (len(line) for line in self.toPlainText().expandtabs(4).splitlines()), default=0
        )
        return widest * self.fontMetrics().horizontalAdvance("9") > self.viewport().width() - 8

    # -- lit lines ---------------------------------------------------------
    def highlight_lines(self, lines: Iterable[int], *, scroll: bool = True) -> None:
        """Light these 1-based lines (an empty iterable clears them) and, with
        ``scroll``, bring the first into view."""
        self._lit = sorted({n for n in lines if 1 <= n <= self.blockCount()})
        self._paint_lit()
        if scroll and self._lit:
            block = self.document().findBlockByNumber(self._lit[0] - 1)
            cursor = QTextCursor(block)
            self.setTextCursor(cursor)
            self.centerCursor()

    def lit_lines(self) -> list[int]:
        return list(self._lit)

    def _paint_lit(self) -> None:
        selections: list[QTextEdit.ExtraSelection] = []
        for n in self._lit:
            block = self.document().findBlockByNumber(n - 1)
            if not block.isValid():
                continue
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(self._colors["line"])
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = QTextCursor(block)
            selections.append(selection)
        self.setExtraSelections(selections)
        self._gutter.update()

    # -- clicks ----------------------------------------------------------
    def line_at(self, y: int) -> int | None:
        """The 1-based line at viewport height ``y``, if any."""
        block = self.firstVisibleBlock()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        while block.isValid():
            bottom = top + self.blockBoundingRect(block).height()
            if top <= y < bottom:
                return block.blockNumber() + 1
            top = bottom
            block = block.next()
        return None

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and not self.textCursor().hasSelection():
            line = self.line_at(int(event.position().y()))
            if line is not None:
                self.line_clicked.emit(line)

    # -- the gutter --------------------------------------------------------
    def gutter_width(self) -> int:
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 2 * GUTTER_PAD + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margins(self, *_: object) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _scroll_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        rect = self.contentsRect()
        self._gutter.setGeometry(QRect(rect.left(), rect.top(), self.gutter_width(), rect.height()))
        if self._fit is not None and event.size().width() != event.oldSize().width():
            self.fit_height(*self._fit)

    def paint_gutter(self, event: QPaintEvent) -> None:
        painter = QPainter(self._gutter)
        font = QFont(self.font())
        painter.setFont(font)
        width = self._gutter.width()
        height = self.fontMetrics().height()
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        lit = set(self._lit)
        while block.isValid() and top <= event.rect().bottom():
            bottom = top + round(self.blockBoundingRect(block).height())
            if block.isVisible() and bottom >= event.rect().top():
                number = block.blockNumber() + 1
                if number in lit:
                    painter.fillRect(0, top, MARK_WIDTH, bottom - top, self._colors["mark"])
                    painter.fillRect(
                        MARK_WIDTH, top, width - MARK_WIDTH, bottom - top, self._colors["line"]
                    )
                    painter.setPen(QColor(self._colors["mark"]))
                else:
                    painter.setPen(QColor(self._colors["gutter"]))
                painter.drawText(
                    0,
                    top,
                    width - GUTTER_PAD,
                    height,
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                    str(number),
                )
            block = block.next()
            top = bottom
        painter.end()
