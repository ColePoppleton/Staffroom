"""Table widgets: a Qt model over :class:`~teaching_tools.core.table.Table`, a
read-only preview and an editable grid (e.g. grade boundaries)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QPushButton,
    QStackedLayout,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from teaching_tools.core.panel import Column, EditableTable, PresetRows, TablePreview
from teaching_tools.core.table import Cell, Row, Table, coerce

Index = QModelIndex | QPersistentModelIndex


class TableModel(QAbstractTableModel):
    def __init__(self, table: Table | None = None, *, editable: bool = False) -> None:
        super().__init__()
        self._table = table or Table([], [])
        self._editable = editable
        self._kinds: dict[int, str] = {}

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


class TableWidget(QTableView):
    """A QTableView with the kit's default look and behaviour."""

    def __init__(self, model: TableModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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

    def fit_columns(self) -> None:
        self.resizeColumnsToContents()
        header = self.horizontalHeader()
        for i in range(header.count()):
            header.resizeSection(i, min(max(header.sectionSize(i) + 16, 90), 320))

    def fit_rows(self, max_rows: int = 12) -> None:
        """Grow to show up to ``max_rows`` rows; beyond that, scroll."""
        model = self.model()
        rows = min(model.rowCount(), max_rows) if model else 0
        row_h = self.verticalHeader().defaultSectionSize()
        height = self.horizontalHeader().height() + rows * row_h + 2
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
            preset_row.addWidget(self.save_button)
            layout.addLayout(preset_row)
        layout.addWidget(self.view)
        if spec.can_add_rows:
            buttons = QHBoxLayout()
            self.add_button = QPushButton("Add row")
            self.add_button.setProperty("role", "ghost")
            self.add_button.clicked.connect(self.add_row)
            self.remove_button = QPushButton("Remove selected")
            self.remove_button.setProperty("role", "ghost")
            self.remove_button.clicked.connect(self.remove_selected)
            buttons.addWidget(self.add_button)
            buttons.addWidget(self.remove_button)
            buttons.addStretch(1)
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
