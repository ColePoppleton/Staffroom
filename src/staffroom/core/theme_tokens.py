"""Colour tokens shared by the Qt shell and anything that renders images
(charts). Qt-free so tools may import it.

The Staffroom scheme: manila card for the grounds, navy ink for text and a
red-pen accent, in a light and a dark reading."""

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
    window="#1b1a17",
    sidebar="#211f1b",
    surface="#25231f",
    surface_alt="#171613",
    border="#35322c",
    border_strong="#46423a",
    text="#efe9dc",
    text_muted="#a39e92",
    text_faint="#6d685c",
    accent="#ff6b5e",
    accent_hover="#ff8276",
    accent_pressed="#e2554a",
    accent_soft="#3d2522",
    on_accent="#1b1a17",
    danger="#ff7a6e",
    success="#5ad48f",
    selection="#4a2a27",
    scrollbar="#3b372f",
    code_string="#9fd6a4",
    code_number="#f2b86b",
    code_builtin="#cfa6ff",
    code_name="#7fd0e0",
)

LIGHT = Palette(
    window="#f4efe3",
    sidebar="#fbf8f0",
    surface="#fbf8f0",
    surface_alt="#f1ecdf",
    border="#e3dccb",
    border_strong="#cfc6b0",
    text="#1c2433",
    text_muted="#6b6a62",
    text_faint="#9b978a",
    accent="#c8322b",
    accent_hover="#d8463f",
    accent_pressed="#a82820",
    accent_soft="#f7e0dd",
    on_accent="#ffffff",
    danger="#b3261e",
    success="#1f7a3a",
    selection="#f1d5d1",
    scrollbar="#d9d2bf",
    code_string="#1f7a3a",
    code_number="#a3490a",
    code_builtin="#6a3fc9",
    code_name="#0b6a7a",
)

PALETTES: dict[str, Palette] = {"dark": DARK, "light": LIGHT}


def palette(theme: str) -> Palette:
    return PALETTES.get(theme, DARK)
