"""Generate a form from a dataclass and read an instance back out.

Supported field types: ``bool``, ``int``, ``float``, ``str``, ``Literal[...]``
of strings, and ``Enum`` subclasses. Field ``metadata`` keys: ``label``,
``help``, ``min``, ``max``, ``step``.

With ``presets`` (:class:`~staffroom.core.panel.OptionsPreset`) the form
starts with a Preset dropdown. Choosing a preset sets the fields it pins;
editing any field afterwards moves the dropdown to whichever preset still
matches the values, or to "Custom" when none does.
"""

from __future__ import annotations

import dataclasses
import enum
import types
import typing
from collections.abc import Callable, Iterable
from typing import Any

from PySide6.QtCore import Qt, Signal, SignalInstance
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from staffroom.core.panel import OptionsPreset, matching_preset

CUSTOM = "Custom"


class OptionsFormWidget(QWidget):
    changed = Signal()

    def __init__(
        self,
        schema: type,
        presets: Iterable[OptionsPreset] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not dataclasses.is_dataclass(schema):
            msg = f"OptionsForm schema must be a dataclass, got {schema!r}"
            raise TypeError(msg)
        self.schema = schema
        self.presets: tuple[OptionsPreset, ...] = tuple(presets)
        self.widgets: dict[str, QWidget] = {}
        self._getters: dict[str, Callable[[], Any]] = {}
        self._setters: dict[str, Callable[[Any], None]] = {}
        self._syncing = False
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.preset_combo: QComboBox | None = None
        if self.presets:
            self.preset_combo = QComboBox()
            self.preset_combo.setObjectName("optionsPreset")
            for p in self.presets:
                self.preset_combo.addItem(p.name)
            self.preset_combo.setToolTip(
                "Choosing a preset sets the fields below. Edit a field and the preset "
                "becomes Custom."
            )
            self.preset_combo.currentTextChanged.connect(self._preset_chosen)
            label = QLabel("Preset")
            label.setProperty("role", "muted")
            layout.addRow(label, self.preset_combo)

        hints = typing.get_type_hints(schema)
        defaults = schema()
        for f in dataclasses.fields(schema):
            label_text = f.metadata.get("label", f.name.replace("_", " ").capitalize())
            widget, getter, setter, edited = self._make_widget(
                hints[f.name], getattr(defaults, f.name), f.metadata
            )
            if help_text := f.metadata.get("help"):
                widget.setToolTip(help_text)
            label = QLabel(label_text)
            label.setProperty("role", "muted")
            layout.addRow(label, widget)
            self.widgets[f.name] = widget
            self._getters[f.name] = getter
            self._setters[f.name] = setter
            edited.connect(lambda *_: self._field_edited())
        self._sync_preset_combo()

    def value(self) -> Any:
        return self.schema(**{name: get() for name, get in self._getters.items()})

    # -- presets -----------------------------------------------------------
    def current_preset(self) -> str:
        """The dropdown's text: a preset name, or "Custom"."""
        return self.preset_combo.currentText() if self.preset_combo else CUSTOM

    def apply_preset(self, name: str) -> None:
        """Set the fields pinned by the preset called ``name``; others are left alone."""
        chosen = next((p for p in self.presets if p.name == name), None)
        if chosen is None:
            return
        self._syncing = True
        try:
            for field_name, value in chosen.values:
                self._setters[field_name](value)
        finally:
            self._syncing = False
        self._sync_preset_combo()
        self.changed.emit()

    def _preset_chosen(self, name: str) -> None:
        if not self._syncing and name != CUSTOM:
            self.apply_preset(name)

    def _field_edited(self) -> None:
        if self._syncing:
            return
        self._sync_preset_combo()
        self.changed.emit()

    def _sync_preset_combo(self) -> None:
        """Point the dropdown at the preset the values match, or at Custom."""
        combo = self.preset_combo
        if combo is None:
            return
        match = matching_preset(self.presets, self.value())
        combo.blockSignals(True)
        try:
            custom_at = combo.findText(CUSTOM)
            if match is not None:
                if custom_at >= 0:
                    combo.removeItem(custom_at)
                combo.setCurrentText(match.name)
            else:
                if custom_at < 0:
                    combo.addItem(CUSTOM)
                combo.setCurrentText(CUSTOM)
        finally:
            combo.blockSignals(False)

    # -- widget factory --------------------------------------------------
    def _make_widget(
        self, hint: Any, default: Any, meta: typing.Mapping[str, Any]
    ) -> tuple[QWidget, Callable[[], Any], Callable[[Any], None], SignalInstance]:
        """The widget for a field, its getter, its setter and its "edited" signal."""
        origin = typing.get_origin(hint)
        if origin in (typing.Union, types.UnionType):
            args = [a for a in typing.get_args(hint) if a is not type(None)]
            hint, origin = args[0], typing.get_origin(args[0])

        if origin is typing.Literal:
            choices = [str(c) for c in typing.get_args(hint)]
            combo = QComboBox()
            combo.addItems(choices)
            combo.setCurrentText(str(default))
            return (
                combo,
                combo.currentText,
                lambda v: combo.setCurrentText(str(v)),
                combo.currentIndexChanged,
            )

        if isinstance(hint, type) and issubclass(hint, enum.Enum):
            members = list(hint)
            combo = QComboBox()
            for m in members:
                combo.addItem(str(m.value), m)
            combo.setCurrentIndex(members.index(default))
            return (
                combo,
                combo.currentData,
                lambda v: combo.setCurrentIndex(members.index(v)),
                combo.currentIndexChanged,
            )

        if hint is bool:
            box = QCheckBox()
            box.setChecked(bool(default))
            return box, box.isChecked, lambda v: box.setChecked(bool(v)), box.toggled

        if hint is int:
            spin = QSpinBox()
            spin.setRange(int(meta.get("min", -1_000_000)), int(meta.get("max", 1_000_000)))
            spin.setSingleStep(int(meta.get("step", 1)))
            spin.setValue(int(default))
            return spin, spin.value, lambda v: spin.setValue(int(v)), spin.valueChanged

        if hint is float:
            dspin = QDoubleSpinBox()
            dspin.setRange(float(meta.get("min", -1e9)), float(meta.get("max", 1e9)))
            dspin.setSingleStep(float(meta.get("step", 0.5)))
            dspin.setDecimals(int(meta.get("decimals", 2)))
            dspin.setValue(float(default))
            return dspin, dspin.value, lambda v: dspin.setValue(float(v)), dspin.valueChanged

        edit = QLineEdit(str(default) if default is not None else "")
        return (
            edit,
            edit.text,
            lambda v: edit.setText("" if v is None else str(v)),
            edit.textChanged,
        )
