"""A results table fitted to the screen (``ResultsTable`` with ``compact``,
``lift_constants``, ``mark_changes`` or ``pin_last``; see
:class:`~staffroom.core.panel.ResultsTable`).

Top to bottom:

* the lifted line: columns that never change once set leave the table for
  one line of chips above it ("Never changes after line 2: scores = […]");
* the table: the main view with its columns sized to their values, and, with
  ``pin_last``, a second view on the same model showing only the last column,
  held at the right edge. The two share one selection model and one vertical
  scroll, so a row is one row across both; the vertical scroll bar sits at
  the far right, on the pinned view, and the main view scrolls sideways
  under it only when its columns cannot all fit;
* the caption (row count, and what bold and grey mean).

The tool's table is untouched: lifted and pinned columns are hidden in the
main view, not removed, so line links and tests read the same model."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.panel import Constant, ResultsTable, change_marks, constant_columns
from staffroom.core.table import Cell, Table
from staffroom.shell.widgets.flow_layout import FlowLayout
from staffroom.shell.widgets.table_view import TableModel, TableWidget

COMPACT_MIN = 36  # narrowest column: a one-digit value and its padding
COMPACT_MAX = 180  # widest column; a longer value is cut and shown in full on hover
COMPACT_EXTRA = 2  # breathing room past the widest value (the cell padding is the rest)
PIN_MIN = 80  # the pinned column never narrower than this...
PIN_SHARE = 0.45  # ...nor wider than this share of the table, unless there is room to spare
MAIN_MIN = 120  # the scrolling part keeps at least this much
CHIP_CHARS = 60  # a lifted value longer than this is cut (in full on hover)
LEGEND = "bold: changed on this line · grey: carried down"


def _shown(value: Cell) -> str:
    return "" if value is None else f"{value:g}" if isinstance(value, float) else str(value)


def lifted_phrase(constants: list[Constant]) -> tuple[str, list[str]]:
    """The lead-in and one chip per constant: "Never changes after line 2:"
    and ``scores = [45, 62]`` when they share a line; otherwise each chip
    says its own line."""
    lines = {c.line for c in constants}
    same = len(lines) == 1 and None not in lines
    verb = "Never changes" if len(constants) == 1 else "Never change"
    if same:
        lead = f"{verb} after line {_shown(constants[0].line)}:"
    elif lines == {None}:
        lead = f"{verb}:"
    else:
        lead = "Never change once set:"
    chips = []
    for c in constants:
        text = f"{c.column} = {_shown(c.value)}"
        if not same and c.line is not None:
            text += f" (line {_shown(c.line)})"
        chips.append(text)
    return lead, chips


class FitTable(QWidget):
    """The view, its lifted line, its pinned column and caption, for one
    ``ResultsTable`` spec. Call :meth:`refresh` after the model gets a table
    (and the view its hints)."""

    def __init__(
        self,
        spec: ResultsTable,
        model: TableModel,
        view: TableWidget,
        caption: QLabel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.model = model
        self.view = view
        self.caption = caption
        self.constants: list[Constant] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.lifted = QWidget()
        self.lifted.setObjectName("LiftedLine")
        self._flow = FlowLayout(self.lifted, spacing=8)
        self.lifted.setVisible(False)
        layout.addWidget(self.lifted)

        self.frame = QFrame()
        self.frame.setObjectName("FitTableFrame")
        row = QHBoxLayout(self.frame)
        row.setContentsMargins(1, 1, 1, 1)
        row.setSpacing(0)
        row.addWidget(view)
        self.pinned: TableWidget | None = None
        if spec.pin_last:
            self.pinned = self._pinned_view()
            row.addWidget(self.pinned, 1)
            view.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        else:
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.frame, 1)
        layout.addWidget(caption)

    def _pinned_view(self) -> TableWidget:
        pinned = TableWidget(self.model)
        pinned.setObjectName("PinnedColumn")
        pinned.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        pinned.setSelectionModel(self.view.selectionModel())
        # The one column fills the pinned view, however narrow the view is.
        pinned.horizontalHeader().setMinimumSectionSize(COMPACT_MIN)
        pinned.viewport().installEventFilter(self)
        pinned.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the keys work in the main view
        pinned.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # One vertical scroll for both, its bar at the far right.
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pinned.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        ours, theirs = self.view.verticalScrollBar(), pinned.verticalScrollBar()
        ours.valueChanged.connect(theirs.setValue)
        theirs.valueChanged.connect(ours.setValue)
        return pinned

    # -- filling -----------------------------------------------------------
    def refresh(self) -> None:
        """Lift, mark, hide and size for the model's current table."""
        table = self.model.table()
        spec = self.spec
        plain = spec.plain_columns(table)
        self.constants = (
            constant_columns(table, skip=plain, line_column=spec.line_column)
            if spec.lift_constants
            else []
        )
        lifted = {c.column for c in self.constants}
        if spec.mark_changes:
            self.model.set_marks(change_marks(table, skip=(*plain, *lifted)))
        self.model.set_cell_tooltips(spec.compact)
        last = len(table.columns) - 1
        for i, name in enumerate(table.columns):
            if name in lifted or (self.pinned is not None and i == last):
                self.view.setColumnHidden(i, True)
        if self.pinned is not None:
            for i in range(len(table.columns)):
                self.pinned.setColumnHidden(i, i != last)
        self._show_lifted()
        if spec.compact:
            self.view.fit_columns(min_width=COMPACT_MIN, max_width=COMPACT_MAX, extra=COMPACT_EXTRA)
        else:
            self.view.fit_columns()
        self.caption.setText(self.caption_text(table))
        self.refit()

    def caption_text(self, table: Table) -> str:
        rows = len(table.rows)
        text = f"{rows} row{'s' if rows != 1 else ''}"
        return f"{text} · {LEGEND}" if self.spec.mark_changes else text

    def lifted_names(self) -> list[str]:
        return [c.column for c in self.constants]

    def lifted_text(self) -> str:
        """The lifted line as plain text (what the chips say)."""
        if not self.constants:
            return ""
        lead, chips = lifted_phrase(self.constants)
        return f"{lead} {', '.join(chips)}"

    def _show_lifted(self) -> None:
        while (item := self._flow.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self.constants:
            self.lifted.setVisible(False)
            return
        lead, chips = lifted_phrase(self.constants)
        label = QLabel(lead)
        label.setObjectName("LiftedLead")
        self._flow.addWidget(label)
        for text in chips:
            chip = QLabel(text if len(text) <= CHIP_CHARS else text[: CHIP_CHARS - 1] + "…")
            chip.setObjectName("LiftedChip")
            chip.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            if len(text) > CHIP_CHARS:
                chip.setToolTip(text)
            self._flow.addWidget(chip)
        self.lifted.setVisible(True)

    # -- sizing ------------------------------------------------------------
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            self.pinned is not None
            and watched is self.pinned.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self._fill_pinned()
        return super().eventFilter(watched, event)

    def _fill_pinned(self) -> None:
        pinned = self.pinned
        if pinned is not None and self.model.columnCount():
            pinned.setColumnWidth(self.model.columnCount() - 1, pinned.viewport().width())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.refit()

    def _needs_vertical_bar(self) -> bool:
        view = self.view
        rows = sum(view.verticalHeader().sectionSize(r) for r in range(self.model.rowCount()))
        return rows > view.viewport().height()

    def refit(self) -> None:
        """Give the main view the width its columns need, the pinned column
        the rest (at least its value's width, within bounds); when both do
        not fit, the main view gives way and scrolls sideways."""
        pinned = self.pinned
        if pinned is None or self.model.columnCount() == 0:
            return
        last = self.model.columnCount() - 1
        avail = self.frame.contentsRect().width()
        header = pinned.horizontalHeader()
        value = max(header.sectionSizeHint(last), pinned.sizeHintForColumn(last)) + COMPACT_EXTRA
        value = min(value, COMPACT_MAX)
        bar = pinned.verticalScrollBar().sizeHint().width() if self._needs_vertical_bar() else 0
        cap = max(PIN_MIN, int(avail * PIN_SHARE))
        pin_want = max(PIN_MIN, min(value, cap)) + bar + 2 * pinned.frameWidth()
        main_need = self.view.horizontalHeader().length() + 2 * self.view.frameWidth()
        main_width = max(MAIN_MIN, min(main_need, avail - pin_want))
        self.view.setFixedWidth(main_width)
        scrolls = main_need > main_width
        pinned.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
            if scrolls
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._fill_pinned()

    # -- reading (tests, the probe) ----------------------------------------
    def visible_columns(self) -> list[str]:
        """The columns shown in full right now: those of the main view inside
        its viewport, then the pinned one."""
        names: list[str] = []
        horizontal = Qt.Orientation.Horizontal
        views = [self.view] + ([self.pinned] if self.pinned is not None else [])
        for view in views:
            width = view.viewport().width()
            for c in range(self.model.columnCount()):
                if view.isColumnHidden(c):
                    continue
                x = view.columnViewportPosition(c)
                if x >= 0 and x + view.columnWidth(c) <= width:
                    names.append(str(self.model.headerData(c, horizontal)))
        return names
