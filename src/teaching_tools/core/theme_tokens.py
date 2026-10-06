"""Colour tokens shared by the Qt shell and anything that renders images
(charts). Qt-free so tools may import it."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    window: str
    sidebar: str
    surface: str
    surface_alt: str
    border: str
    border_strong: str
    text: str
    text_muted: str
    text_faint: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    on_accent: str
    danger: str
    success: str
    selection: str
    scrollbar: str
    code_string: str
    code_number: str
    code_builtin: str
    code_name: str


DARK = Palette(
    window="#0f1115",
    sidebar="#13161c",
    surface="#191d25",
    surface_alt="#10131a",
    border="#262b36",
    border_strong="#343b49",
    text="#e8ebf1",
    text_muted="#9099ab",
    text_faint="#5d6678",
    accent="#6d8dff",
    accent_hover="#819dff",
    accent_pressed="#5a79e8",
    accent_soft="#1d2540",
    on_accent="#ffffff",
    danger="#ff6b6b",
    success="#3fcf8e",
    selection="#2a3658",
    scrollbar="#2c3240",
    code_string="#8fd19e",
    code_number="#f2b86b",
    code_builtin="#c99bff",
    code_name="#7fd6e6",
)

LIGHT = Palette(
    window="#f2f3f6",
    sidebar="#ffffff",
    surface="#ffffff",
    surface_alt="#f6f7fa",
    border="#e1e4eb",
    border_strong="#c9ced9",
    text="#171a21",
    text_muted="#667085",
    text_faint="#98a2b3",
    accent="#3b5bdb",
    accent_hover="#4c6ce6",
    accent_pressed="#2f4bc0",
    accent_soft="#e8edff",
    on_accent="#ffffff",
    danger="#d13838",
    success="#1f9d6a",
    selection="#dbe3ff",
    scrollbar="#d5d9e2",
    code_string="#1f7a3a",
    code_number="#b4530a",
    code_builtin="#6f3fd6",
    code_name="#0b7285",
)

PALETTES: dict[str, Palette] = {"dark": DARK, "light": LIGHT}


def palette(theme: str) -> Palette:
    return PALETTES.get(theme, DARK)
