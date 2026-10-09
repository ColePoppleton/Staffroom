"""The shell's identity (#89): the brand type is bundled and loaded, the
sidebar glyphs exist and follow the theme, the accent is spent only on
selection, primary actions, links and focus, and muted text is readable."""

from __future__ import annotations

import re

import pytest
from PySide6.QtGui import QFontDatabase, QFontInfo
from PySide6.QtWidgets import QApplication, QPlainTextEdit

from staffroom.core.discovery import visible_plugins
from staffroom.core.plugin import plugin_glyph
from staffroom.core.theme_tokens import PALETTES, Palette
from staffroom.shell.sidebar import LIBRARY_GLYPH
from staffroom.shell.theme import (
    FALLBACK_GLYPH,
    FONTS,
    MONO,
    MONO_FAMILY,
    SANS,
    SERIF,
    glyph_names,
    glyph_path,
    glyph_pixmap,
    load_fonts,
    stylesheet,
)


def test_each_bundled_font_ships_with_its_ofl_licence() -> None:
    fonts = sorted(p.name for p in FONTS.glob("*.ttf"))
    assert fonts, "no bundled fonts"
    for family in ("Fraunces", "SourceSans3", "IBMPlexMono"):
        assert any(name.startswith(family) for name in fonts), family
        licence = (FONTS / f"{family}-OFL.txt").read_text(encoding="utf-8")
        assert "SIL Open Font License, Version 1.1" in licence


def test_fonts_load_and_the_stylesheet_uses_them(qapp: QApplication) -> None:
    families = load_fonts()
    assert {SANS, SERIF, MONO} <= set(families)
    assert load_fonts() == families  # once per process
    for family in (SANS, SERIF, MONO):
        assert family in QFontDatabase.families()
    qss = stylesheet("dark")
    assert f'font-family: "{SANS}", -apple-system' in qss  # the old stack is the fallback
    assert f'"{SERIF}", Georgia' in qss
    for view in ("QPlainTextEdit#CodeView", "QPlainTextEdit#LogView"):
        rule = qss[qss.index(view) : qss.index("}", qss.index(view))]
        assert MONO_FAMILY in rule


def test_code_views_render_in_plex_mono(qapp: QApplication) -> None:
    load_fonts()
    view = QPlainTextEdit()
    view.setObjectName("CodeView")
    view.setStyleSheet(stylesheet("light"))
    view.ensurePolished()
    assert QFontInfo(view.font()).family() == MONO


def test_every_glyph_a_tool_names_is_bundled() -> None:
    names = set(glyph_names())
    wanted = {plugin_glyph(p) for p in visible_plugins()} | {LIBRARY_GLYPH, FALLBACK_GLYPH}
    assert wanted <= names
    for name in names:
        assert "currentColor" in glyph_path(name).read_text(encoding="utf-8")  # themable


def test_unknown_glyph_falls_back_and_paints(qapp: QApplication) -> None:
    assert glyph_path("no-such-glyph").stem == FALLBACK_GLYPH
    assert glyph_path("../icon").stem == FALLBACK_GLYPH
    pixmap = glyph_pixmap("no-such-glyph", PALETTES["dark"].text_muted)
    assert not pixmap.isNull()
    assert pixmap.deviceIndependentSize().width() == 14


_ACCENT_ALLOWED = re.compile(
    r"current|:checked|:focus|:selected|primary|link|::chunk|:pressed|Progress"
)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_accent_is_spent_on_selection_primary_links_and_focus(theme: str) -> None:
    p = PALETTES[theme]
    accents = {p.accent, p.accent_hover, p.accent_pressed}
    offenders = []
    for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", stylesheet(theme)):  # type: ignore[arg-type]
        selector = selector.split("*/")[-1].strip()
        if any(colour in body for colour in accents) and not _ACCENT_ALLOWED.search(selector):
            offenders.append(selector)
    assert offenders == []


def _luminance(hex_colour: str) -> float:
    rgb = [int(hex_colour.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast(fg: str, bg: str) -> float:
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_muted_text_reads_at_aa_on_every_ground(theme: str) -> None:
    """Group names, the footer, counts and subtitles are text_muted; the
    current row's name is text on accent_soft. All at least 4.5:1."""
    p: Palette = PALETTES[theme]
    for ground in (p.window, p.sidebar, p.surface, p.surface_alt):
        assert contrast(p.text_muted, ground) >= 4.5, (theme, ground)
    assert contrast(p.text, p.accent_soft) >= 4.5
    assert contrast(p.on_accent, p.accent) >= 4.5  # primary buttons
