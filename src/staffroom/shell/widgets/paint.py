"""Helpers for widgets that paint: colours the stylesheet sets.

A painted widget declares ``barColor = color_property("bar")`` and keeps a
``_colors`` dict; ``shell/theme.py`` sets the colour with
``qproperty-barColor: <token>``, so no colour is written in widget code and a
theme change repaints."""

from __future__ import annotations

from PySide6.QtCore import Property
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget


def color_property(name: str) -> Property:
    """A ``QColor`` Qt property stored in the widget's ``_colors[name]``."""

    def get(self: QWidget) -> QColor:
        return self._colors[name]  # type: ignore[attr-defined, no-any-return]

    def set_(self: QWidget, color: QColor) -> None:
        self._colors[name] = QColor(color)  # type: ignore[attr-defined]
        self.update()

    return Property(QColor, get, set_)


def default_colors(*names: str) -> dict[str, QColor]:
    """Placeholders until the stylesheet is applied (e.g. a bare test widget)."""
    return {name: QColor(128, 128, 128) for name in names}
