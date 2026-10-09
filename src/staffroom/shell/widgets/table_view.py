"""Table widgets: a Qt model over :class:`~staffroom.core.table.Table`, a
read-only preview and an editable grid (e.g. grade boundaries).

A results table can carry hints (:class:`~staffroom.core.panel.ResultsTable`):
numeric columns drawn with an inline bar, a tag beside the first cell, and
hidden columns whose values go to the row's tooltip. :class:`ReportDelegate`
paints the bars and tags in colours the stylesheet sets on
:class:`TableWidget` (``qproperty-barColor`` …)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QRectF,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QPushButton,
    QStackedLayout,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.panel import BarColumn, Column, EditableTable, PresetRows, TablePreview
from staffroom.core.table import Cell, Row, Table, coerce
from staffroom.shell.widgets.choice import ChoiceWidget
from staffroom.shell.widgets.paint import color_property, default_colors

Index = QModelIndex | QPersistentModelIndex
TAG_ROLE = Qt.ItemDataRole.UserRole + 1  # the row's tag text, on any cell
NUMBER_ROLE = Qt.ItemDataRole.UserRole + 2  # the cell as a float, or None
TAGGED_ROW_HEIGHT = 42  # a tagged row: its text and the tag under it


class TableModel(QAbstractTableModel):
    def __init__(self, table: Table | None = None, *, editable: bool = False) -> None:
        super().__init__()
        self._table = table or Table([], [])
        self._editable = editable
        self._kinds: dict[int, str] = {}
        self._tag_column: str | None = None
        self._tooltip_columns: tuple[str, ...] = ()

    # -- data access -----------------------------------------------------
    def table(self) -> Table:
        return Table(
            list(self._table.columns), [list(r) for r in self._table.rows], self._table.fake_data
        )

    def set_table(self, table: Table | None) -> None:
        self.beginResetModel()
        self._table = table or Table([], [])
        self.endResetModel()

    def set_kinds(self, columns: tuple[Column, ...]) -> None:
        self._kinds = {i: c.kind for i, c in enumerate(columns)}

    def set_hints(
        self, tag_column: str | None = None, tooltip_columns: tuple[str, ...] = ()
    ) -> None:
        """``tag_column``'s text is offered on every cell as :data:`TAG_ROLE`;
        ``tooltip_columns`` make up each row's tooltip."""
        self._tag_column = tag_column
        self._tooltip_columns = tooltip_columns

    def tag(self, row: int) -> str:
        if self._tag_column is None or self._tag_column not in self._table.columns:
            return ""
        value = self._table.rows[row][self._table.columns.index(self._tag_column)]
        return "" if value is None else str(value)

    def _tooltip(self, row: int) -> str | None:
        lines = []
        for name in self._tooltip_columns:
            if name in self._table.columns:
                value = self._table.rows[row][self._table.columns.index(name)]
                if value not in (None, ""):
                    lines.append(f"{name}: {value}")
        return "\n".join(lines) or None

    # -- Qt model API ----------------------------------------------------
    def rowCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._table.rows)

    def columnCount(self, parent: Index = QModelIndex()) -> int:  # noqa: B008, N802
        return 0 if parent.isValid() else len(self._table.columns)

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self._table.columns[section]
        return section + 1

    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None
        value = self._table.rows[index.row()][index.column()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            if value is None:
                return ""
            if isinstance(value, float):
                return f"{value:g}"
            return str(value)
        if role == Qt.ItemDataRole.TextAlignmentRole and isinstance(value, int | float):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._tooltip(index.row())
        if role == TAG_ROLE:
            return self.tag(index.row())
        if role == NUMBER_ROLE:
            if isinstance(value, bool) or not isinstance(value, int | float):
                return None
            return float(value)
        return None

    def flags(self, index: Index) -> Qt.ItemFlag:
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return base | Qt.ItemFlag.ItemIsEditable if self._editable else base

    def setData(self, index: Index, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:  # noqa: N802
        if not (index.isValid() and self._editable and role == Qt.ItemDataRole.EditRole):
            return False
        kind = self._kinds.get(index.column(), "text")
        cell = _coerce_kind(value, kind)
        self._table.rows[index.row()][index.column()] = cell
        self.dataChanged.emit(index, index, [role])
        return True

    # -- row editing -----------------------------------------------------
    def append_row(self, row: Row | None = None) -> None:
        n = len(self._table.rows)
        self.beginInsertRows(QModelIndex(), n, n)
        self._table.rows.append(row if row is not None else [None] * len(self._table.columns))
        self.endInsertRows()

    def remove_rows(self, rows: list[int]) -> None:
        for r in sorted(set(rows), reverse=True):
            self.beginRemoveRows(QModelIndex(), r, r)
            del self._table.rows[r]
            self.endRemoveRows()


def _coerce_kind(value: Any, kind: str) -> Cell:
    text = "" if value is None else str(value).strip()
    if text == "":
        return None
    if kind == "int":
        try:
            return int(float(text))
        except ValueError:
            return None
    if kind == "float":
        try:
            return float(text)
        except ValueError:
            return None
    if kind == "bool":
        return text.lower() in {"1", "true", "yes", "y"}
    return coerce(text) if kind == "text" else text


class ReportDelegate(QStyledItemDelegate):
    """Paints the hinted cells of a :class:`TableWidget`: an inline bar beside
    the number in ``bars`` columns (the action colour for a tagged row), and the row's
    tag as a small outlined label after the first cell's text."""

    BAR_WIDTH = 40
    GAP = 6

    def __init__(self, view: TableWidget, bars: dict[int, BarColumn]) -> None:
        super().__init__(view)
        self.view = view
        self.bars = bars

    def _tag_font(self, option: QStyleOptionViewItem) -> QFont:
        font = QFont(option.font)
        font.setPixelSize(10)
        font.setBold(True)
        return font

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: Index) -> None:
        bar = self.bars.get(index.column())
        tag = str(index.data(TAG_ROLE) or "") if index.column() == 0 else ""
        if bar is None and not tag:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        rect = opt.rect.adjusted(8, 0, -8, 0)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = self.view.colors()
        painter.setPen(colors["text"])
        if bar is not None:
            number = index.data(NUMBER_ROLE)
            share = 0.0 if number is None or bar.maximum <= 0 else number / bar.maximum
            share = max(0.0, min(1.0, share))
            track = QRectF(rect.left(), rect.center().y() - 3, self.BAR_WIDTH, 6)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(colors["track"])
            painter.drawRoundedRect(track, 3, 3)
            tagged = bool(index.data(TAG_ROLE))
            painter.setBrush(colors["action"] if tagged else colors["bar"])
            painter.drawRoundedRect(
                QRectF(track.left(), track.top(), track.width() * share, 6), 3, 3
            )
            painter.setPen(colors["text"])
            text_rect = QRect(rect)
            text_rect.setLeft(int(track.right()) + self.GAP)
            painter.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter), text)
        else:  # the text on the upper line, the tag under it
            painter.drawText(
                QRect(rect.left(), rect.top() + 3, rect.width(), rect.height() // 2),
                int(Qt.AlignmentFlag.AlignBottom),
                text,
            )
            font = self._tag_font(opt)
            tag_metrics = QFontMetrics(font)
            chip = QRectF(
                rect.left(), rect.center().y() + 2, tag_metrics.horizontalAdvance(tag) + 12, 15
            )
            painter.setPen(colors["action"])
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(chip.adjusted(0.5, 0.5, -0.5, -0.5), 7.5, 7.5)
            painter.setFont(font)
            painter.drawText(chip, int(Qt.AlignmentFlag.AlignCenter), tag)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: Index) -> QSize:  # noqa: N802
        size = super().sizeHint(option, index)
        if index.column() in self.bars:
            size.setWidth(size.width() + self.BAR_WIDTH + self.GAP)
        elif index.column() == 0 and (tag := str(index.data(TAG_ROLE) or "")):
            chip = QFontMetrics(self._tag_font(option)).horizontalAdvance(tag) + 12
            size.setWidth(max(size.width(), chip + 16))
            size.setHeight(max(size.height(), TAGGED_ROW_HEIGHT))
        return size


class TableWidget(QTableView):
    """A QTableView with the kit's default look and behaviour."""

    # Inline bars and tags (ReportDelegate): set in shell/theme.py.
    barColor = color_property("bar")  # noqa: N815
    actionColor = color_property("action")  # noqa: N815
    trackColor = color_property("track")  # noqa: N815
    textColor = color_property("text")  # noqa: N815

    def __init__(self, model: TableModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._colors = default_colors("bar", "action", "track", "text")
        self.setModel(model)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(30)
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(70)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setMinimumHeight(80)

    def colors(self) -> dict[str, Any]:
        return self._colors

    def set_hints(
        self,
        *,
        bars: tuple[BarColumn, ...] = (),
        tag_column: str | None = None,
        hidden_columns: tuple[str, ...] = (),
    ) -> None:
        """Apply a ResultsTable's display hints (see :mod:`core.panel`). Call
        before ``set_table``; columns are matched by name on every fill."""
        model = self.model()
        assert isinstance(model, TableModel)
        hidden = tuple(hidden_columns) + ((tag_column,) if tag_column else ())
        model.set_hints(tag_column, tuple(hidden_columns))
        self.setProperty("action", bool(tag_column))  # tagged rows ask to be acted on
        self._hint_bars = bars
        self._hidden = hidden
        self._delegate: ReportDelegate | None = None

    def apply_hints(self) -> None:
        """After the model has a table: hide columns, attach the bar delegate."""
        model = self.model()
        columns = model._table.columns if isinstance(model, TableModel) else []
        hidden = getattr(self, "_hidden", ())
        for i, name in enumerate(columns):
            self.setColumnHidden(i, name in hidden)
        bars = {
            columns.index(b.name): b for b in getattr(self, "_hint_bars", ()) if b.name in columns
        }
        has_tag = bool(isinstance(model, TableModel) and model._tag_column)
        if bars or has_tag:
            self._delegate = ReportDelegate(self, bars)
            self.setItemDelegate(self._delegate)

    def fit_columns(self, min_width: int = 90, max_width: int = 320, extra: int = 16) -> None:
        """Size columns to their contents plus ``extra``, within the bounds;
        a tagged row (see ReportDelegate) gets the height for its tag."""
        header = self.horizontalHeader()
        header.setMinimumSectionSize(min(70, min_width))
        self.resizeColumnsToContents()
        for i in range(header.count()):
            if not header.isSectionHidden(i):
                size = header.sectionSize(i) + extra
                header.resizeSection(i, min(max(size, min_width), max_width))
        model = self.model()
        if getattr(self, "_delegate", None) is not None and isinstance(model, TableModel):
            for row in range(model.rowCount()):
                if model.tag(row):
                    self.verticalHeader().resizeSection(row, TAGGED_ROW_HEIGHT)

    def fit_rows(self, max_rows: int = 12) -> None:
        """Grow to show up to ``max_rows`` rows; beyond that, scroll."""
        model = self.model()
        rows = min(model.rowCount(), max_rows) if model else 0
        vertical = self.verticalHeader()
        height = self.horizontalHeader().height() + 2
        height += sum(vertical.sectionSize(r) for r in range(rows))
        if rows < (model.rowCount() if model else 0):
            height += self.horizontalScrollBar().sizeHint().height()
        self.setFixedHeight(max(height, 80))


class TablePreviewWidget(QWidget):
    """Read-only table with an empty state and a row-count caption."""

    def __init__(self, spec: TablePreview, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.model = TableModel()
        self.view = TableWidget(self.model)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.empty = QLabel("Choose a file to preview it here.")
        self.empty.setProperty("role", "empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.caption = QLabel("")
        self.caption.setProperty("role", "faint")

        self.stack = QStackedLayout()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.view)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(self.stack)
        layout.addWidget(self.caption)

    def set_table(self, table: Table | None) -> None:
        if table is None or not table.columns:
            self.model.set_table(None)
            self.stack.setCurrentWidget(self.empty)
            self.caption.setText("")
            return
        shown = (
            table
            if len(table) <= self.spec.max_rows
            else Table(table.columns, table.rows[: self.spec.max_rows], table.fake_data)
        )
        self.model.set_table(shown)
        self.view.fit_columns()
        self.view.fit_rows()
        self.stack.setCurrentWidget(self.view)
        rows, cols = table.shape
        note = f"{rows} rows × {cols} columns"
        if len(shown) < rows:
            note += f" (showing first {len(shown)})"
        if table.fake_data:
            note += "  ·  fake data"
        if table.dropped_columns:
            note += "  ·  dropped identifier columns: " + ", ".join(table.dropped_columns)
        self.caption.setText(note)

    def set_error(self, message: str) -> None:
        self.model.set_table(None)
        self.stack.setCurrentWidget(self.empty)
        self.caption.setText(message)


class EditableTableWidget(QWidget):
    """A small editable grid with add/remove row buttons and optional presets."""

    changed = Signal()
    preset_saved = Signal(str, object)  # name, Table

    def __init__(self, spec: EditableTable, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        columns = [c.name for c in spec.columns]
        rows: list[Row] = [list(r) for r in spec.rows]
        self.model = TableModel(Table(columns, rows), editable=True)
        self.model.set_kinds(spec.columns)
        self.model.dataChanged.connect(lambda *_: self.changed.emit())
        self.view = TableWidget(self.model)
        self.view.fit_rows(8)
        self.model.rowsInserted.connect(lambda *_: self.view.fit_rows(8))
        self.model.rowsRemoved.connect(lambda *_: self.view.fit_rows(8))
        for i, col in enumerate(spec.columns):
            if col.width:
                self.view.horizontalHeader().resizeSection(i, col.width)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.presets: dict[str, PresetRows] = {}
        if spec.presets:
            preset_row = QHBoxLayout()
            preset_row.setSpacing(8)
            label = QLabel("Preset")
            label.setProperty("role", "muted")
            self.preset_combo = QComboBox()
            # Sized to a short name, not the longest one: the inputs pane is narrow.
            self.preset_combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            self.preset_combo.setMinimumContentsLength(10)
            for name, preset_rows in spec.presets:
                self.presets[name] = preset_rows
                self.preset_combo.addItem(name)
            self.apply_button = QPushButton("Apply")
            self.apply_button.clicked.connect(self.apply_preset)
            self.save_button = QPushButton("Save as preset…")
            self.save_button.setProperty("role", "ghost")
            self.save_button.setVisible(spec.preset_action is not None)
            self.save_button.clicked.connect(self.save_preset)
            preset_row.addWidget(label)
            preset_row.addWidget(self.preset_combo, 1)
            preset_row.addWidget(self.apply_button)
            layout.addLayout(preset_row)
        self.choice: ChoiceWidget | None = None
        if spec.choice is not None:
            choice_row = QHBoxLayout()
            choice_label = QLabel(spec.choice.label)
            choice_label.setProperty("role", "muted")
            self.choice = ChoiceWidget(spec.choice)
            choice_row.addWidget(choice_label)
            choice_row.addWidget(self.choice)
            choice_row.addStretch(1)
            layout.addLayout(choice_row)
        layout.addWidget(self.view)
        # Row buttons on the left, saving the grid as a preset on the right.
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        if spec.can_add_rows:
            self.add_button = QPushButton("Add row")
            self.add_button.setProperty("role", "ghost")
            self.add_button.clicked.connect(self.add_row)
            self.remove_button = QPushButton("Remove row")
            self.remove_button.setToolTip("Remove the selected rows")
            self.remove_button.setProperty("role", "ghost")
            self.remove_button.clicked.connect(self.remove_selected)
            buttons.addWidget(self.add_button)
            buttons.addWidget(self.remove_button)
        buttons.addStretch(1)
        if spec.presets:
            buttons.addWidget(self.save_button)
        if buttons.count() > 1:
            layout.addLayout(buttons)

    def add_row(self) -> None:
        self.model.append_row()
        self.view.scrollToBottom()
        self.changed.emit()

    def remove_selected(self) -> None:
        rows = [i.row() for i in self.view.selectionModel().selectedRows()]
        if rows:
            self.model.remove_rows(rows)
            self.changed.emit()

    def value(self) -> Table:
        return self.model.table()

    def choice_value(self) -> str | None:
        return self.choice.value() if self.choice else None

    def set_rows(self, rows: list[Row]) -> None:
        columns = [c.name for c in self.spec.columns]
        self.model.set_table(Table(columns, [list(r) for r in rows]))
        self.view.fit_rows(8)
        self.changed.emit()

    def apply_preset(self, name: str | None = None) -> None:
        name = name or self.preset_combo.currentText()
        rows = self.presets.get(name)
        if rows is not None:
            self.set_rows([list(r) for r in rows])

    def add_preset(self, name: str, rows: list[Row]) -> None:
        self.presets[name] = tuple(tuple(r) for r in rows)
        if self.preset_combo.findText(name) < 0:
            self.preset_combo.addItem(name)
        self.preset_combo.setCurrentText(name)

    def save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:")
        name = name.strip()
        if ok and name:
            table = self.value()
            self.add_preset(name, table.rows)
            self.preset_saved.emit(name, table)
