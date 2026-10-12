"""Toggle chips for a :class:`~staffroom.core.panel.ChipChoice`: any number
on at once, wrapping onto as many lines as they need, each with its count
small after its name (*binary 4*). Notes the tool returns for the input
(a running total) show under the chips; ``empty_text`` shows while there
are none."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from staffroom.core.panel import ChipChoice, ChipOption, Note
from staffroom.shell.widgets.card import make_label
from staffroom.shell.widgets.flow_layout import FlowLayout

TICK, WARN = "✓", "!"


def chip_text(option: ChipOption) -> str:
    """What a chip says: its name, then its count if it has one."""
    return option.shown if option.count is None else f"{option.shown} {option.count}"


class ToggleChip(QPushButton):
    """A checkable pill: the name, and its count small and faint after it.
    The two labels follow the chip's state through an ``on`` property."""

    def __init__(self, option: ChipOption, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.option = option
        self.setObjectName("ToggleChip")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(chip_text(option))
        self.setToolTip(option.shown if option.count is None else f"{option.shown}: {option.count}")
        row = QHBoxLayout(self)
        row.setContentsMargins(11, 4, 11, 4)
        row.setSpacing(5)
        self.name = QLabel(option.shown)
        self.name.setObjectName("ChipName")
        self.count = QLabel("" if option.count is None else str(option.count))
        self.count.setObjectName("ChipCount")
        self.count.setVisible(option.count is not None)
        for label in (self.name, self.count):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            row.addWidget(label)
        self.toggled.connect(lambda _on: self.sync())
        self.sync()

    def sizeHint(self) -> QSize:  # noqa: N802
        layout = self.layout()
        return layout.sizeHint() if layout is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def sync(self) -> None:
        """Restyle the chip and its labels for its state."""
        on = self.isChecked()
        for widget in (self, self.name, self.count):
            widget.setProperty("on", "true" if on else "false")
            widget.style().unpolish(widget)
            widget.style().polish(widget)


class ChipChoiceWidget(QWidget):
    changed = Signal(object)  # the new value: a tuple of the values that are on

    def __init__(self, spec: ChipChoice, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.options: tuple[ChipOption, ...] = ()
        self.chips: dict[str, ToggleChip] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.area = QWidget()
        self.area.setObjectName("ChipArea")
        self.flow = FlowLayout(self.area, spacing=6)
        layout.addWidget(self.area)
        self.empty = make_label(spec.empty_text, "faint", wrap=True)
        layout.addWidget(self.empty)
        self.note_labels: list[QLabel] = []
        self._notes = QVBoxLayout()
        self._notes.setSpacing(2)
        layout.addLayout(self._notes)
        self.set_options(spec.options)

    # -- value ---------------------------------------------------------------
    def value(self) -> tuple[str, ...]:
        return tuple(o.value for o in self.options if self.chips[o.value].isChecked())

    def set_value(self, values: Iterable[str]) -> None:
        """Turn on exactly the chips named (unknown values are ignored)."""
        wanted = set(values)
        before = self.value()
        for value, chip in self.chips.items():
            chip.blockSignals(True)
            chip.setChecked(value in wanted)
            chip.blockSignals(False)
            chip.sync()
        if self.value() != before:
            self.changed.emit(self.value())

    def set_options(self, options: Iterable[ChipOption]) -> bool:
        """New chips (a new bank's topics). Chips that were on stay on while
        the new options still have them. Says nothing (no ``changed``);
        returns whether the value changed, so the caller can re-inspect."""
        before = self.value() if self.options else ()
        options = tuple(options)
        if options == self.options:
            return False
        for chip in self.chips.values():
            self.flow.removeWidget(chip)
            chip.deleteLater()
        self.chips = {}
        self.options = options
        for option in options:
            chip = ToggleChip(option)
            chip.setChecked(option.value in before)
            chip.toggled.connect(lambda _on: self.changed.emit(self.value()))
            self.flow.addWidget(chip)
            self.chips[option.value] = chip
        self.area.setVisible(bool(options))
        self.empty.setVisible(not options and bool(self.spec.empty_text))
        self.flow.invalidate()
        self.area.updateGeometry()
        return self.value() != before

    # -- notes ---------------------------------------------------------------
    def set_notes(self, notes: Iterable[Note]) -> None:
        for label in self.note_labels:
            self._notes.removeWidget(label)
            label.deleteLater()
        self.note_labels = []
        for note in notes:
            label = make_label(note.text if note.ok else f"{WARN} {note.text}", "", wrap=True)
            label.setProperty("role", "note-ok" if note.ok else "note-warn")
            self._notes.addWidget(label)
            self.note_labels.append(label)

    def notes(self) -> list[str]:
        return [label.text() for label in self.note_labels]
