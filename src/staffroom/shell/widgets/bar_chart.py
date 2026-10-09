"""A bar chart drawn by the shell (:class:`~staffroom.core.panel.BarChart`):
crisp at any size and in the theme's colours, with the count over each bar
and the category and its detail (e.g. a percentage) under it. A switch flips
the same rows to a table.

Colours come from the stylesheet (``qproperty-barColor`` and friends on
``BarCanvas`` in ``shell/theme.py``), never from this file."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QPushButton,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.panel import BarChart
from staffroom.core.table import Cell, Table
from staffroom.shell.widgets.paint import color_property, default_colors
from staffroom.shell.widgets.table_view import TableModel, TableWidget

SLOT = 22  # px per bar, label included
SLOT_MIN = 17
BAR_MAX = 30  # px: wide panes space the bars out, not fatten them
BAR_SHARE = 0.62  # of the slot
PAD_X = 4
TOP_ROOM = 18  # the count over the tallest bar
LABEL_ROOM = 34  # category and detail under the bars
HEIGHT = 196
MAX_HEIGHT = 300  # beside a long table the bars stop growing


@dataclass(frozen=True)
class Bar:
    category: str
    value: float
    detail: str


def _number(value: Cell) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return 0.0


def bars_from_table(spec: BarChart, table: Table) -> list[Bar]:
    """The bars ``spec`` draws from ``table``: skipped categories left out."""
    out: list[Bar] = []
    if spec.category not in table.columns or spec.value not in table.columns:
        return out
    for record in table.to_dicts():
        category = "" if record[spec.category] is None else str(record[spec.category])
        if category in spec.skip:
            continue
        detail = ""
        if spec.detail and spec.detail in record and record[spec.detail] is not None:
            raw = record[spec.detail]
            detail = spec.detail_format.format(raw) if isinstance(raw, int | float) else str(raw)
        out.append(Bar(category, _number(record[spec.value]), detail))
    return out


def _count(value: float) -> str:
    return f"{value:g}"


class BarCanvas(QWidget):
    """Paints the bars. Width follows the number of bars; height is fixed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bars: list[Bar] = []
        self._colors = default_colors("bar", "text", "muted", "faint", "axis")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(HEIGHT)
        self.setMaximumHeight(MAX_HEIGHT)

    # -- colours from the stylesheet (qproperty-barColor: ... in theme.py) -----
    barColor = color_property("bar")  # noqa: N815
    textColor = color_property("text")  # noqa: N815
    mutedColor = color_property("muted")  # noqa: N815
    faintColor = color_property("faint")  # noqa: N815
    axisColor = color_property("axis")  # noqa: N815

    def color(self, name: str) -> QColor:
        return self._colors[name]

    # -- data ----------------------------------------------------------------
    def set_bars(self, bars: list[Bar]) -> None:
        self.bars = bars
        self.updateGeometry()
        self.update()

    def natural_width(self) -> int:
        return max(len(self.bars), 1) * SLOT + 2 * PAD_X

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.natural_width(), HEIGHT)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(max(len(self.bars), 1) * SLOT_MIN + 2 * PAD_X, HEIGHT)

    # -- painting --------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        if not self.bars:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        n = len(self.bars)
        slot = (self.width() - 2 * PAD_X) / n
        base_y = self.height() - LABEL_ROOM
        room = base_y - TOP_ROOM
        top = max((b.value for b in self.bars), default=0.0) or 1.0
        base_font = QFont(self.font())
        small = QFont(base_font)
        small.setPixelSize(9)
        bold = QFont(base_font)
        bold.setPixelSize(12)
        bold.setBold(True)
        count_font = QFont(bold)
        count_font.setPixelSize(11)

        painter.setPen(self._colors["axis"])
        painter.drawLine(PAD_X, base_y, self.width() - PAD_X, base_y)
        for i, bar in enumerate(self.bars):
            x = PAD_X + i * slot
            width = min(slot * BAR_SHARE, BAR_MAX)
            height = room * bar.value / top
            if bar.value > 0:
                rect = QRectF(x + (slot - width) / 2, base_y - height, width, height)
                painter.fillRect(rect, self._colors["bar"])
                painter.setFont(count_font)
                painter.setPen(self._colors["text"])
                painter.drawText(
                    QRectF(x - 4, rect.top() - 16, slot + 8, 14),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                    _count(bar.value),
                )
            painter.setFont(bold)
            painter.setPen(self._colors["text"])
            painter.drawText(
                QRectF(x - 6, base_y + 3, slot + 12, 15),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                bar.category,
            )
            if bar.detail:
                painter.setFont(small)
                painter.setPen(self._colors["muted"] if bar.value > 0 else self._colors["faint"])
                painter.drawText(
                    QRectF(x - 6, base_y + 18, slot + 12, 14),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    bar.detail,
                )
        painter.end()


class BarChartWidget(QWidget):
    """The canvas and the same rows as a table, one at a time; ``toggle``
    (placed by the output pane in the view's heading) flips between them."""

    def __init__(self, spec: BarChart, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.canvas = BarCanvas()
        self.model = TableModel()
        self.table_view = TableWidget(self.model)
        self.table_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stack = QStackedLayout()
        self.stack.addWidget(self.canvas)
        self.stack.addWidget(self.table_view)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.stack)
        self.toggle = QPushButton("Table")
        self.toggle.setProperty("role", "link")
        self.toggle.setToolTip("Show the numbers as a table")
        self.toggle.clicked.connect(self.flip)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

    def set_table(self, table: Table | None) -> None:
        self.model.set_table(table)
        self.canvas.set_bars(bars_from_table(self.spec, table) if table else [])
        if table is not None:
            self.table_view.fit_columns(min_width=48)
            self.table_view.setMinimumHeight(HEIGHT)
        self.updateGeometry()

    def showing_table(self) -> bool:
        return self.stack.currentWidget() is self.table_view

    def flip(self) -> None:
        to_table = not self.showing_table()
        self.stack.setCurrentWidget(self.table_view if to_table else self.canvas)
        self.toggle.setText("Chart" if to_table else "Table")
        self.toggle.setToolTip(
            "Show the chart again" if to_table else "Show the numbers as a table"
        )

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.canvas.natural_width(), HEIGHT)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.canvas.minimumSizeHint()
