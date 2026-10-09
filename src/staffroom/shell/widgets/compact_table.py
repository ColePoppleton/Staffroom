"""The compact form of an :class:`~staffroom.core.panel.EditableTable`: a
two-column (label, number) table as a grid of small cells, ``per_row`` to a
line, each label beside its editable number. Ten grade boundaries take two
lines instead of a ten-row table that scrolls inside its card.

It keeps the same model and the same interface as
:class:`EditableTableWidget` (``value``, ``set_rows``, presets, ``changed``,
``preset_saved``), so the tool sees a :class:`Table` either way."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.panel import EditableTable, PresetRows
from staffroom.core.table import Row, Table
from staffroom.shell.widgets.choice import ChoiceWidget
from staffroom.shell.widgets.table_view import TableModel


def _number_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


class GridCell(QFrame):
    """One label and its number."""

    edited = Signal(str)

    def __init__(self, label: str, value: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("GridCell")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 2, 0)
        layout.setSpacing(2)
        self.label = QLabel(label)
        self.label.setObjectName("GridLabel")
        self.edit = QLineEdit(_number_text(value))
        self.edit.setObjectName("GridValue")
        self.edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        validator = QDoubleValidator(0.0, 1e6, 2, self.edit)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.edit.setValidator(validator)
        self.edit.setAccessibleName(f"Minimum for {label}")
        self.edit.setToolTip(f"Minimum for {label}")
        self.edit.textEdited.connect(self.edited.emit)
        layout.addWidget(self.label)
        layout.addWidget(self.edit, 1)


class CompactTableWidget(QWidget):
    changed = Signal()
    preset_saved = Signal(str, object)  # name, Table

    def __init__(self, spec: EditableTable, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        columns = [c.name for c in spec.columns]
        self.model = TableModel(Table(columns, [list(r) for r in spec.rows]), editable=True)
        self.model.set_kinds(spec.columns)
        self.cells: list[GridCell] = []
        self.presets: dict[str, PresetRows] = dict(spec.presets)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.preset_combo = QComboBox()
        self.preset_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.preset_combo.setMinimumContentsLength(10)
        self.preset_combo.setToolTip("Choosing a preset fills the boundaries below")
        for name in self.presets:
            self.preset_combo.addItem(name)
        start = next((n for n, rows in self.presets.items() if rows == spec.rows), None)
        if start is not None:
            self.preset_combo.setCurrentText(start)
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        self.preset_combo.setVisible(bool(self.presets))
        layout.addWidget(self.preset_combo)

        self.choice: ChoiceWidget | None = None
        if spec.choice is not None:
            row = QHBoxLayout()
            row.setSpacing(10)
            label = QLabel(spec.choice.label)
            label.setProperty("role", "muted")
            self.choice = ChoiceWidget(spec.choice)
            row.addWidget(label)
            row.addWidget(self.choice)
            row.addStretch(1)
            layout.addLayout(row)

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(6)
        self.grid.setVerticalSpacing(6)
        layout.addLayout(self.grid)

        # Placed in the group's heading by the tool panel (a link, like the mockup).
        self.save_button = QPushButton("Save as preset")
        self.save_button.setProperty("role", "link")
        self.save_button.setToolTip("Keep these boundaries as a named preset")
        self.save_button.setVisible(spec.preset_action is not None)
        self.save_button.clicked.connect(self.save_preset)
        self._rebuild()

    # -- the grid ------------------------------------------------------------
    def _rebuild(self) -> None:
        for cell in self.cells:
            self.grid.removeWidget(cell)
            cell.deleteLater()
        self.cells = []
        per_row = max(1, self.spec.per_row)
        for i, row in enumerate(self.model.table().rows):
            cell = GridCell(_number_text(row[0]), row[1])
            cell.edited.connect(lambda text, r=i: self._edited(r, text))
            self.grid.addWidget(cell, i // per_row, i % per_row)
            self.cells.append(cell)
        for c in range(per_row):
            self.grid.setColumnStretch(c, 1)

    def _edited(self, row: int, text: str) -> None:
        self.model.setData(self.model.index(row, 1), text)
        self.changed.emit()

    # -- the EditableTableWidget interface ------------------------------------
    def value(self) -> Table:
        return self.model.table()

    def choice_value(self) -> str | None:
        return self.choice.value() if self.choice else None

    def set_rows(self, rows: list[Row]) -> None:
        columns = [c.name for c in self.spec.columns]
        self.model.set_table(Table(columns, [list(r) for r in rows]))
        self._rebuild()
        self.changed.emit()

    def apply_preset(self, name: str | None = None) -> None:
        name = name or self.preset_combo.currentText()
        rows = self.presets.get(name)
        if rows is not None:
            self.set_rows([list(r) for r in rows])

    def add_preset(self, name: str, rows: list[Row]) -> None:
        self.presets[name] = tuple(tuple(r) for r in rows)
        self.preset_combo.blockSignals(True)
        if self.preset_combo.findText(name) < 0:
            self.preset_combo.addItem(name)
        self.preset_combo.setCurrentText(name)
        self.preset_combo.blockSignals(False)

    def save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:")
        name = name.strip()
        if ok and name:
            table = self.value()
            self.add_preset(name, table.rows)
            self.preset_saved.emit(name, table)
