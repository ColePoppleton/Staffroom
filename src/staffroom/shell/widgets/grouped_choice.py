"""A :class:`~staffroom.core.panel.GroupedChoice`: the groups as exclusive chips
(a unit), the chosen group's items as a list of rows under a small heading (its
lessons). A row shows its name, a tag at the right (a spec point) and a detail
line; a dim row is faint, with the reason in place of the tag, and can still be
chosen. A divided row has a rule above it (a unit's Review)."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.panel import ChipOption, GroupedChoice, GroupedItem
from staffroom.shell.widgets.card import make_label
from staffroom.shell.widgets.chip_choice import ToggleChip
from staffroom.shell.widgets.elided_label import ElidedLabel
from staffroom.shell.widgets.flow_layout import FlowLayout
from staffroom.shell.widgets.input_group import eyebrow


def _restyle(widget: QWidget, **props: str) -> None:
    for name, value in props.items():
        widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ListRow(QPushButton):
    """One checkable row: the name and its tag on the first line, the detail
    under them. Its labels follow its state through ``on`` and ``dim``."""

    def __init__(self, item: GroupedItem, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.item = item
        self.setObjectName("ListRow")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tag = item.note if item.dim and item.note else item.tag
        self.setAccessibleName(f"{item.text}, {tag}" if tag else item.text)
        self.setToolTip(item.note or item.detail)
        grid = QGridLayout(self)
        grid.setContentsMargins(10, 6, 10, 7)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(1)
        self.name = ElidedLabel(item.text)
        self.name.setObjectName("RowText")
        self.tag = QLabel(tag)
        self.tag.setObjectName("RowTag")
        self.tag.setVisible(bool(tag))
        self.detail = ElidedLabel(item.detail)
        self.detail.setObjectName("RowDetail")
        self.detail.setVisible(bool(item.detail))
        grid.addWidget(self.name, 0, 0)
        grid.addWidget(self.tag, 0, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(self.detail, 1, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        for label in (self.name, self.tag, self.detail):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.toggled.connect(lambda _on: self.sync())
        self.sync()

    def sizeHint(self) -> QSize:  # noqa: N802
        layout = self.layout()
        return layout.sizeHint() if layout is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        hint = self.sizeHint()
        return QSize(0, hint.height())

    def sync(self) -> None:
        on = "true" if self.isChecked() else "false"
        dim = "true" if self.item.dim else "false"
        for widget in (self, self.name, self.tag, self.detail):
            _restyle(widget, on=on, dim=dim)


class GroupedChoiceWidget(QWidget):
    changed = Signal(str)  # the chosen item's value

    def __init__(self, spec: GroupedChoice, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self._value = spec.initial
        self._last: dict[str, str] = {}  # group -> the item last chosen in it
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.area = QWidget()
        self.area.setObjectName("ChipArea")
        self.flow = FlowLayout(self.area, spacing=6)
        layout.addWidget(self.area)
        self.items_label = eyebrow(spec.items_label)
        layout.addSpacing(6)
        layout.addWidget(self.items_label)
        self.rows_box = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_box)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(2)
        layout.addWidget(self.rows_box)
        self.note = make_label(spec.note, "faint", wrap=True)
        self.note.setVisible(bool(spec.note))
        layout.addWidget(self.note)
        self.chip_group = QButtonGroup(self)
        self.chip_group.setExclusive(True)
        self.row_group = QButtonGroup(self)
        self.row_group.setExclusive(True)
        self.chips: dict[str, ToggleChip] = {}
        self.rows: dict[str, ListRow] = {}
        self._shown_group = ""
        self._build_chips()
        self._show_group(self._group_of(self._value))

    # -- value ---------------------------------------------------------------
    def value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        """Choose ``value`` (an unknown one is ignored); says ``changed`` if it moved."""
        group = self._group_of(value)
        if not group:
            return
        before = self._value
        self._value = value
        self._last[group] = value
        self._show_group(group)
        if value != before:
            self.changed.emit(value)

    def set_spec(self, spec: GroupedChoice) -> None:
        """New groups and rows (the board changed in Settings), keeping the item
        chosen while the new spec still has it."""
        if spec == self.spec:
            return
        self.spec = spec
        self.note.setText(spec.note)
        self.note.setVisible(bool(spec.note))
        values = {v for v, _ in spec.choices}
        if self._value not in values:
            self._value = spec.initial
        self._build_chips()
        self._shown_group = ""
        self._show_group(self._group_of(self._value))

    # -- building ------------------------------------------------------------
    def _group_of(self, value: str) -> str:
        group = self.spec.group_of(value)
        return group.value if group is not None else ""

    def _build_chips(self) -> None:
        for chip in self.chips.values():
            self.chip_group.removeButton(chip)
            self.flow.removeWidget(chip)
            chip.deleteLater()
        self.chips = {}
        for group in self.spec.groups:
            chip = ToggleChip(ChipOption(group.value, group.text))
            chip.setToolTip(group.note or group.text)
            for widget in (chip, chip.name):
                _restyle(widget, dim="true" if group.dim else "false")
            self.chip_group.addButton(chip)
            chip.clicked.connect(lambda _c=False, g=group.value: self._choose_group(g))
            self.flow.addWidget(chip)
            self.chips[group.value] = chip
        self.flow.invalidate()
        self.area.updateGeometry()

    def _choose_group(self, value: str) -> None:
        group = next(g for g in self.spec.groups if g.value == value)
        last = self._last.get(value)
        if last is None or self._group_of(last) != value:
            last = next((i.value for i in group.items if not i.dim), group.items[0].value)
        self.set_value(last)

    def _show_group(self, value: str) -> None:
        for key, chip in self.chips.items():
            chip.blockSignals(True)
            chip.setChecked(key == value)
            chip.blockSignals(False)
            chip.sync()
        if value != self._shown_group:
            self._shown_group = value
            for row in self.rows.values():
                self.row_group.removeButton(row)
                row.deleteLater()
            while self.rows_layout.count():
                taken = self.rows_layout.takeAt(0)
                widget = taken.widget() if taken is not None else None
                if widget is not None:
                    widget.deleteLater()
            self.rows = {}
            group = next(g for g in self.spec.groups if g.value == value)
            for item in group.items:
                if item.divided:
                    rule = QFrame()
                    rule.setObjectName("Divider")
                    rule.setFixedHeight(1)
                    self.rows_layout.addWidget(rule)
                row = ListRow(item)
                row.clicked.connect(lambda _c=False, v=item.value: self.set_value(v))
                self.row_group.addButton(row)
                self.rows_layout.addWidget(row)
                self.rows[item.value] = row
        for key, row in self.rows.items():
            row.blockSignals(True)
            row.setChecked(key == self._value)
            row.blockSignals(False)
            row.sync()
