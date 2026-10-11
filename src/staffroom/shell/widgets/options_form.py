"""Generate a form from a dataclass and read an instance back out.

Supported field types: ``bool``, ``int``, ``float``, ``str``, ``Literal[...]``
of strings, and ``Enum`` subclasses. Field ``metadata`` keys: ``label``,
``help``, ``min``, ``max``, ``step``.

With ``presets`` (:class:`~staffroom.core.panel.OptionsPreset`) the form
starts with a Preset dropdown. Choosing a preset sets the fields it pins;
editing any field afterwards moves the dropdown to whichever preset still
matches the values, or to "Custom" when none does.

Built from an :class:`~staffroom.core.panel.OptionsForm` (:meth:`OptionsFormWidget.for_spec`)
the form also hides the fields that do not apply (``shown_when``), shows a
choice's values by their labels (``choice_labels``) and draws the
``switches`` as segmented switches. A hidden field keeps what was set in it;
:meth:`OptionsFormWidget.value` hands the tool its default instead.
"""

from __future__ import annotations

import dataclasses
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
    QSizePolicy,
    QSpinBox,
    QWidget,
)

from staffroom.core.panel import (
    Choice,
    OptionsForm,
    OptionsPreset,
    choice_key,
    choice_values,
    matching_preset,
)
from staffroom.shell.widgets.choice import ChoiceWidget

CUSTOM = "Custom"
LABEL_MAX_WIDTH = 112


def _narrow(combo: QComboBox) -> None:
    """Size a combo to a short entry, not its longest one (the popup still
    shows every entry in full), so a form fits the narrow inputs pane."""
    combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(10)


class OptionsFormWidget(QWidget):
    changed = Signal()

    def __init__(
        self,
        schema: type,
        presets: Iterable[OptionsPreset] = (),
        parent: QWidget | None = None,
        *,
        fields: Iterable[str] = (),
        spec: OptionsForm | None = None,
    ) -> None:
        super().__init__(parent)
        if not dataclasses.is_dataclass(schema):
            msg = f"OptionsForm schema must be a dataclass, got {schema!r}"
            raise TypeError(msg)
        self.schema = schema
        # The spec carries shown_when, choice_labels and switches; a form built
        # from a bare schema has none of them.
        self.spec = spec if spec is not None else OptionsForm(key="options", schema=schema)
        self._defaults = schema()
        self.presets: tuple[OptionsPreset, ...] = tuple(presets)
        self.widgets: dict[str, QWidget] = {}
        self._getters: dict[str, Callable[[], Any]] = {}
        self._setters: dict[str, Callable[[Any], None]] = {}
        self._syncing = False
        self._layout = layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.preset_combo: QComboBox | None = None
        if self.presets:
            self.preset_combo = QComboBox()
            self.preset_combo.setObjectName("optionsPreset")
            _narrow(self.preset_combo)
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
        shown = set(fields)
        for f in dataclasses.fields(schema):
            if shown and f.name not in shown:
                continue  # left at its default (another input may set it)
            label_text = f.metadata.get("label", f.name.replace("_", " ").capitalize())
            default = getattr(self._defaults, f.name)
            values = choice_values(schema, f.name)
            if values is not None:
                widget, getter, setter, edited = self._make_choice(
                    f.name, label_text, values, default, f.metadata
                )
            else:
                widget, getter, setter, edited = self._make_widget(
                    hints[f.name], default, f.metadata
                )
            if help_text := f.metadata.get("help"):
                widget.setToolTip(help_text)
            label = QLabel(label_text)
            label.setProperty("role", "muted")
            # A long label wraps in its column rather than pushing the form
            # wider than the narrow inputs pane.
            label.setWordWrap(True)
            natural = label.fontMetrics().horizontalAdvance(label_text) + 4
            label.setMinimumWidth(min(natural, LABEL_MAX_WIDTH))
            label.setMaximumWidth(LABEL_MAX_WIDTH)
            layout.addRow(label, widget)
            self.widgets[f.name] = widget
            self._getters[f.name] = getter
            self._setters[f.name] = setter
            edited.connect(lambda *_: self._field_edited())
        self._sync_visibility()
        self._sync_preset_combo()

    @classmethod
    def for_spec(cls, spec: OptionsForm, parent: QWidget | None = None) -> OptionsFormWidget:
        return cls(spec.schema, spec.presets, parent, fields=spec.fields, spec=spec)

    def held(self) -> Any:
        """Everything the form holds, hidden fields included."""
        return self.schema(**{name: get() for name, get in self._getters.items()})

    def value(self) -> Any:
        """The options for the tool: what the form holds, with every field
        that does not apply (hidden) at its default."""
        return self.spec.passed(self.held())

    def set_field(self, name: str, value: Any) -> None:
        """Set one field of the form, as if the teacher had edited it."""
        self._setters[name](value)

    def shown_fields(self) -> list[str]:
        """The fields whose rows are on screen, in form order."""
        return [n for n, w in self.widgets.items() if self._layout.isRowVisible(w)]

    def _sync_visibility(self) -> None:
        hidden = self.spec.hidden(self.held())
        for name in self.spec.shown_when:
            widget = self.widgets.get(name)
            if widget is not None:
                self._layout.setRowVisible(widget, name not in hidden)

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
        self._sync_visibility()
        self._sync_preset_combo()
        self.changed.emit()

    def _preset_chosen(self, name: str) -> None:
        if not self._syncing and name != CUSTOM:
            self.apply_preset(name)

    def _field_edited(self) -> None:
        if self._syncing:
            return
        self._sync_visibility()
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
    def _make_choice(
        self,
        name: str,
        label: str,
        values: tuple[Any, ...],
        default: Any,
        meta: typing.Mapping[str, Any],
    ) -> tuple[QWidget, Callable[[], Any], Callable[[Any], None], SignalInstance]:
        """A ``Literal`` or ``Enum`` field: a dropdown, or a segmented switch
        when the spec lists it in ``switches``, showing each value's label.
        The getter returns the value itself (the member, for an ``Enum``); the
        setter takes the value, or its text (``--option level=a_level``)."""
        keys = [choice_key(v) for v in values]
        by_key = dict(zip(keys, values, strict=True))

        if name in self.spec.switches:
            switch = ChoiceWidget(
                Choice(
                    key=name,
                    label=label,
                    choices=tuple((k, self.spec.label_for(name, v)) for k, v in by_key.items()),
                    default=choice_key(default),
                    help=meta.get("help", ""),
                )
            )
            return (
                switch,
                lambda: by_key[switch.value()],
                lambda v: switch.set_value(choice_key(v)),
                switch.changed,
            )

        combo = QComboBox()
        _narrow(combo)
        # A labelled choice reads as words, not a code value: let it use the
        # width of the field column so the label is not cut short.
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for v in values:
            combo.addItem(self.spec.label_for(name, v), v)

        def select(v: Any) -> None:
            if choice_key(v) in keys:  # an unknown value leaves the choice as it was
                combo.setCurrentIndex(keys.index(choice_key(v)))

        select(default)
        return combo, lambda: values[combo.currentIndex()], select, combo.currentIndexChanged

    def _make_widget(
        self, hint: Any, default: Any, meta: typing.Mapping[str, Any]
    ) -> tuple[QWidget, Callable[[], Any], Callable[[Any], None], SignalInstance]:
        """The widget for a field, its getter, its setter and its "edited" signal."""
        if typing.get_origin(hint) in (typing.Union, types.UnionType):
            hint = next(a for a in typing.get_args(hint) if a is not type(None))

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
