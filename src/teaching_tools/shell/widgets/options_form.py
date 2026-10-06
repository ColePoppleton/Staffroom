"""Generate a form from a dataclass and read an instance back out.

Supported field types: ``bool``, ``int``, ``float``, ``str``, ``Literal[...]``
of strings, and ``Enum`` subclasses. Field ``metadata`` keys: ``label``,
``help``, ``min``, ``max``, ``step``.
"""

from __future__ import annotations

import dataclasses
import enum
import types
import typing
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt
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


class OptionsFormWidget(QWidget):
    def __init__(self, schema: type, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if not dataclasses.is_dataclass(schema):
            msg = f"OptionsForm schema must be a dataclass, got {schema!r}"
            raise TypeError(msg)
        self.schema = schema
        self._getters: dict[str, Callable[[], Any]] = {}
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(16)
        layout.setVerticalSpacing(10)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        hints = typing.get_type_hints(schema)
        defaults = schema()
        for f in dataclasses.fields(schema):
            label_text = f.metadata.get("label", f.name.replace("_", " ").capitalize())
            widget, getter = self._make_widget(hints[f.name], getattr(defaults, f.name), f.metadata)
            if help_text := f.metadata.get("help"):
                widget.setToolTip(help_text)
            label = QLabel(label_text)
            label.setProperty("role", "muted")
            layout.addRow(label, widget)
            self._getters[f.name] = getter

    def value(self) -> Any:
        return self.schema(**{name: get() for name, get in self._getters.items()})

    # -- widget factory --------------------------------------------------
    def _make_widget(
        self, hint: Any, default: Any, meta: typing.Mapping[str, Any]
    ) -> tuple[QWidget, Callable[[], Any]]:
        origin = typing.get_origin(hint)
        if origin in (typing.Union, types.UnionType):
            args = [a for a in typing.get_args(hint) if a is not type(None)]
            hint, origin = args[0], typing.get_origin(args[0])

        if origin is typing.Literal:
            choices = [str(c) for c in typing.get_args(hint)]
            combo = QComboBox()
            combo.addItems(choices)
            combo.setCurrentText(str(default))
            return combo, combo.currentText

        if isinstance(hint, type) and issubclass(hint, enum.Enum):
            members = list(hint)
            combo = QComboBox()
            for m in members:
                combo.addItem(str(m.value), m)
            combo.setCurrentIndex(members.index(default))
            return combo, combo.currentData

        if hint is bool:
            box = QCheckBox()
            box.setChecked(bool(default))
            return box, box.isChecked

        if hint is int:
            spin = QSpinBox()
            spin.setRange(int(meta.get("min", -1_000_000)), int(meta.get("max", 1_000_000)))
            spin.setSingleStep(int(meta.get("step", 1)))
            spin.setValue(int(default))
            return spin, spin.value

        if hint is float:
            dspin = QDoubleSpinBox()
            dspin.setRange(float(meta.get("min", -1e9)), float(meta.get("max", 1e9)))
            dspin.setSingleStep(float(meta.get("step", 0.5)))
            dspin.setDecimals(int(meta.get("decimals", 2)))
            dspin.setValue(float(default))
            return dspin, dspin.value

        edit = QLineEdit(str(default) if default is not None else "")
        return edit, edit.text
