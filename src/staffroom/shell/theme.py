"""Design tokens, the brand type, the sidebar glyphs and the generated Qt
stylesheet.

One :class:`Palette` per theme; :func:`stylesheet` turns it into QSS. Widgets
opt into roles with object names (``#Sidebar``, ``#Card``) and dynamic
properties (``role="primary"``, ``role="muted"``) so the kit stays free of
hard-coded colours.

The brand type is bundled (``assets/fonts``, all SIL OFL 1.1, licence files
beside them) so the app and the docs site are one product: Source Sans 3 for
text, Fraunces for the brand and page titles, IBM Plex Mono for code and logs.
:func:`load_fonts` registers them; each family keeps the system fallbacks it
had before, so a missing file degrades to the old look rather than to a
default font.

Glyphs (``assets/glyphs/<name>.svg``) are monochrome line drawings in
``currentColor``; :func:`glyph_pixmap` paints one in a palette colour, so
they follow the theme like everything else.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QFontDatabase, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from staffroom.core.config import Theme
from staffroom.core.log import get_logger
from staffroom.core.theme_tokens import DARK, PALETTES, Palette

__all__ = [
    "DARK",
    "PALETTES",
    "Palette",
    "glyph_icon",
    "glyph_pixmap",
    "load_fonts",
    "palette",
    "stylesheet",
]

log = get_logger(__name__)

SANS = "Source Sans 3"
SERIF = "Fraunces"
MONO = "IBM Plex Mono"
FONT_FAMILY = f'"{SANS}", -apple-system, "SF Pro Text", "Helvetica Neue", "Segoe UI", sans-serif'
SERIF_FAMILY = f'"{SERIF}", Georgia, "Times New Roman", serif'
MONO_FAMILY = f'"{MONO}", "SF Mono", Menlo, Consolas, monospace'
RADIUS = 10
RADIUS_SM = 7
ASSETS = Path(__file__).with_name("assets")
FONTS = ASSETS / "fonts"
GLYPHS = ASSETS / "glyphs"
FALLBACK_GLYPH = "tool"


def asset(name: str) -> str:
    return ASSETS.joinpath(name).as_posix()


def palette(theme: Theme) -> Palette:
    return PALETTES.get(theme, DARK)


_loaded_fonts: tuple[str, ...] | None = None


def load_fonts() -> tuple[str, ...]:
    """Register the bundled fonts with Qt once per process and return the
    families that loaded. Needs a ``QGuiApplication``. A file that fails is
    logged and skipped: the stylesheet's fallbacks take over."""
    global _loaded_fonts
    if _loaded_fonts is None:
        families: list[str] = []
        for path in sorted(FONTS.glob("*.ttf")):
            font_id = QFontDatabase.addApplicationFont(str(path))
            if font_id < 0:
                log.warning("could not load the bundled font %s", path.name)
                continue
            for family in QFontDatabase.applicationFontFamilies(font_id):
                if family not in families:
                    families.append(family)
        _loaded_fonts = tuple(families)
    return _loaded_fonts


def glyph_names() -> list[str]:
    """Every bundled glyph, A-Z: what a plugin's ``glyph`` may name."""
    return sorted(p.stem for p in GLYPHS.glob("*.svg"))


def glyph_path(name: str) -> Path:
    """``assets/glyphs/<name>.svg``, or the generic glyph for an unknown name."""
    path = GLYPHS / f"{name}.svg"
    if not name or "/" in name or not path.is_file():
        path = GLYPHS / f"{FALLBACK_GLYPH}.svg"
    return path


@cache
def glyph_pixmap(name: str, color: str, size: int = 14, ratio: float = 2.0) -> QPixmap:
    """Glyph ``name`` drawn in ``color`` (a palette token) at ``size`` logical
    pixels, rendered at ``ratio`` so it stays sharp on a Retina screen."""
    svg = glyph_path(name).read_text(encoding="utf-8").replace("currentColor", color)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    side = max(1, round(size * ratio))
    pixmap = QPixmap(side, side)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, side, side))
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


def glyph_icon(name: str, color: str, size: int = 14) -> QIcon:
    return QIcon(glyph_pixmap(name, color, size))


def stylesheet(theme: Theme) -> str:
    p = palette(theme)
    check = asset("check.svg")
    chevron = asset(f"chevron-{'light' if theme == 'light' else 'dark'}.svg")
    chevron_right = asset(f"chevron-right-{'light' if theme == 'light' else 'dark'}.svg")
    return f"""
* {{
    font-family: {FONT_FAMILY};
    font-size: 14px;
    color: {p.text};
    outline: none;
}}
QMainWindow, QWidget#Root {{ background: {p.window}; }}
QToolTip {{
    background: {p.surface}; color: {p.text};
    border: 1px solid {p.border_strong}; border-radius: 6px; padding: 6px 8px;
}}

/* ---------------------------------------------------------- typography */
QLabel[role="title"] {{
    font-family: {SERIF_FAMILY}; font-size: 26px; font-weight: 600; letter-spacing: -0.3px;
}}
QLabel[role="subtitle"] {{ font-size: 14px; color: {p.text_muted}; }}
QLabel[role="section"] {{ font-size: 14px; font-weight: 600; color: {p.text}; }}
QLabel[role="muted"] {{ color: {p.text_muted}; }}
QLabel[role="faint"] {{ color: {p.text_faint}; font-size: 12px; }}
QLabel[role="eyebrow"] {{
    color: {p.text_muted}; font-size: 11px; font-weight: 700; letter-spacing: 1px;
}}
QLabel[role="placeholder"] {{ color: {p.text_faint}; font-size: 14px; padding: 24px; }}
QLabel[role="chip"] {{
    background: {p.surface_alt}; color: {p.text_muted}; border: 1px solid {p.border};
    border-radius: 9px; padding: 0px 8px; font-size: 11px; font-weight: 600;
}}
QLabel[role="danger"] {{ color: {p.danger}; }}
QLabel[role="success"] {{ color: {p.success}; }}
QLabel[role="empty"] {{
    color: {p.text_faint}; font-size: 14px;
    border: 1px dashed {p.border_strong}; border-radius: {RADIUS_SM}px; padding: 28px;
}}

/* ---------------------------------------------------------- sidebar
   The accent marks only the current destination (the bar, the glyph, the
   gear when Settings shows) and focus. Group names and the footer use
   text_muted, which clears 4.5:1 on the sidebar in both themes. */
QWidget#Sidebar {{
    background: {p.sidebar};
    border-right: 1px solid {p.border};
}}
QScrollArea#NavScroll, QWidget#NavBody {{ background: transparent; border: none; }}
QLabel#Brand {{
    font-family: {SERIF_FAMILY}; font-size: 20px; font-weight: 600; letter-spacing: -0.2px;
}}
QToolButton#BrandGear {{
    background: transparent; border: 1px solid {p.border}; border-radius: {RADIUS_SM}px;
    min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; padding: 0px;
}}
QToolButton#BrandGear:hover {{ background: {p.surface_alt}; border-color: {p.border_strong}; }}
QToolButton#BrandGear:checked {{ background: {p.accent_soft}; border-color: {p.accent}; }}
QToolButton#BrandGear:focus {{ border-color: {p.accent}; }}
QLineEdit#SidebarSearch {{
    background: {p.surface_alt}; border: 1px solid {p.border_strong}; border-radius: 8px;
    padding: 5px 34px 5px 4px; font-size: 13px;
}}
QLineEdit#SidebarSearch:focus {{ border-color: {p.accent}; }}
QLabel#Kbd {{
    color: {p.text_muted}; font-size: 11px; background: transparent;
    border: 1px solid {p.border}; border-radius: 4px; padding: 0px 4px;
}}
QLabel#NavGroup {{
    color: {p.text_muted}; font-size: 11px; font-weight: 700; letter-spacing: 1px;
    padding: 12px 8px 4px 8px;
}}
QFrame#NavItem {{
    background: transparent; border: 1px solid transparent; border-radius: {RADIUS_SM}px;
}}
QFrame#NavItem:hover {{ background: {p.surface_alt}; }}
QFrame#NavItem[current="true"] {{ background: {p.accent_soft}; }}
QFrame#NavItem:focus {{ border-color: {p.accent}; }}
QLabel#NavText {{ font-size: 14px; font-weight: 600; color: {p.text}; background: transparent; }}
QLabel#NavCount {{ font-size: 12px; color: {p.text_muted}; background: transparent; }}
QLabel#NavGlyph {{
    background: transparent; border: 1px solid {p.border_strong}; border-radius: 6px;
    min-width: 20px; max-width: 20px; min-height: 20px; max-height: 20px;
}}
QLabel#NavGlyph[current="true"] {{ border-color: {p.accent}; }}
QFrame#NavBar {{ background: transparent; border: none; border-radius: 1px; }}
QFrame#NavBar[current="true"] {{ background: {p.accent}; }}
QWidget#SidebarFooter {{ border-top: 1px solid {p.border}; background: transparent; }}
QLabel#SidebarVersion {{ font-size: 12px; color: {p.text_muted}; }}
QPushButton#FooterLink {{
    background: transparent; border: none; padding: 2px 0px; font-size: 12px;
    color: {p.text_muted}; text-align: right;
}}
QPushButton#FooterLink:hover, QPushButton#FooterLink:checked {{ color: {p.text}; }}
QPushButton#FooterLink:focus {{ color: {p.accent}; }}
QPushButton#FooterLink[role="link"] {{ color: {p.accent}; font-weight: 600; }}
QWidget#LibraryColumn {{ background: {p.window}; border-right: 1px solid {p.border}; }}
QTreeView#ResourceTree {{
    background: transparent; border: none; padding: 2px 0px;
    show-decoration-selected: 0;
}}
QDialog#Palette QTreeView#ResourceTree {{
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: {RADIUS_SM}px;
    padding: 6px;
}}
QTreeView#ResourceTree::item {{ padding: 4px 4px; border-radius: 5px; }}
QTreeView#ResourceTree::item:hover {{ background: {p.surface}; }}
QTreeView#ResourceTree::item:selected {{ background: {p.accent_soft}; color: {p.accent}; }}
QTreeView#ResourceTree::branch {{ background: transparent; }}
QTreeView#ResourceTree::branch:has-children:!has-siblings:closed,
QTreeView#ResourceTree::branch:closed:has-children:has-siblings {{
    image: url("{chevron_right}");
}}
QTreeView#ResourceTree::branch:open:has-children:!has-siblings,
QTreeView#ResourceTree::branch:open:has-children:has-siblings {{
    image: url("{chevron}");
}}
QListWidget#ResultList, QListWidget#StringList {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: {RADIUS}px; padding: 6px;
}}
QListWidget#ResultList::item, QListWidget#StringList::item {{
    border-radius: {RADIUS_SM}px; margin: 2px 0px;
}}
QListWidget#ResultList::item:hover, QListWidget#StringList::item:hover {{
    background: {p.surface_alt};
}}
QListWidget#ResultList::item:selected, QListWidget#StringList::item:selected {{
    background: {p.accent_soft};
}}
QListWidget#StringList::item {{ padding: 3px 6px; }}
QPlainTextEdit#CodeView {{
    font-family: {MONO_FAMILY}; font-size: 12.5px; color: {p.text};
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: {RADIUS_SM}px;
}}
QPlainTextEdit#TextView {{
    font-size: 13px; color: {p.text};
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: {RADIUS_SM}px;
}}

/* ---------------------------------------------------------- cards */
QFrame#Card {{
    background: {p.surface};
    border: 1px solid {p.border};
    border-radius: {RADIUS}px;
}}
QFrame#Divider {{ background: {p.border}; max-height: 1px; min-height: 1px; border: none; }}

/* ---------------------------------------------------------- the workbench (tool panels) */
QWidget#PanelHeader {{ background: {p.window}; border-bottom: 1px solid {p.border}; }}
QWidget#InputsPane {{ background: {p.window}; border-right: 1px solid {p.border}; }}
QWidget#RunBar {{ background: {p.sidebar}; }}
QProgressBar#RunProgress {{
    background: {p.border}; border-radius: 0px; min-height: 2px; max-height: 2px;
}}
QProgressBar#RunProgress::chunk {{ background: {p.accent}; border-radius: 0px; }}
QWidget#OutputPane {{ background: {p.surface_alt}; }}
QTabWidget#OutputTabs::pane {{
    background: transparent; border: none; border-top: 1px solid {p.border}; top: -1px;
}}
QTabWidget#OutputTabs > QTabBar {{
    /* the bar's own font sizes the tabs: match the tab text or labels elide */
    background: transparent; font-weight: 600; font-size: 13px;
}}
QTabWidget#OutputTabs > QTabBar::tab {{
    background: transparent; color: {p.text_muted}; font-weight: 600; font-size: 13px;
    border: none; border-bottom: 2px solid transparent; padding: 7px 14px; margin-right: 2px;
}}
QTabWidget#OutputTabs > QTabBar::tab:selected {{
    color: {p.text}; border-bottom-color: {p.accent};
}}
QTabWidget#OutputTabs > QTabBar::tab:hover:!selected {{ color: {p.text}; }}

/* ---------------------------------------------------------- buttons */
QPushButton {{
    background: {p.surface_alt}; color: {p.text};
    border: 1px solid {p.border_strong}; border-radius: {RADIUS_SM}px;
    padding: 6px 14px; min-height: 18px;
}}
QPushButton:hover {{ border-color: {p.text_faint}; }}
QPushButton:pressed {{ background: {p.selection}; }}
QPushButton:disabled {{ color: {p.text_faint}; border-color: {p.border}; }}
QPushButton[role="primary"] {{
    background: {p.accent}; color: {p.on_accent}; border: 1px solid {p.accent};
    font-weight: 600; padding: 8px 20px;
}}
QPushButton[role="primary"]:hover {{
    background: {p.accent_hover}; border-color: {p.accent_hover};
}}
QPushButton[role="primary"]:pressed {{ background: {p.accent_pressed}; }}
QPushButton[role="primary"]:disabled {{
    background: {p.surface_alt}; color: {p.text_faint}; border-color: {p.border};
}}
QPushButton[role="ghost"] {{
    background: transparent; border: 1px solid transparent; color: {p.text_muted}; padding: 4px 8px;
}}
QPushButton[role="ghost"]:hover {{ color: {p.text}; background: {p.surface}; }}
QPushButton[role="link"] {{
    background: transparent; border: none; color: {p.accent}; padding: 2px 4px; text-align: left;
}}
QPushButton[role="link"]:hover {{ text-decoration: underline; }}

/* ---------------------------------------------------------- inputs */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {p.surface_alt}; color: {p.text};
    border: 1px solid {p.border_strong}; border-radius: {RADIUS_SM}px;
    padding: 6px 10px; selection-background-color: {p.selection};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {p.accent};
}}
QLineEdit:read-only {{ color: {p.text_muted}; }}
QLineEdit::placeholder {{ color: {p.text_faint}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 16px; border: none; background: transparent;
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{ image: url("{chevron}"); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
    background: {p.surface}; border: 1px solid {p.border_strong}; border-radius: 6px;
    selection-background-color: {p.selection}; padding: 4px;
}}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid {p.border_strong}; background: {p.surface_alt};
}}
QCheckBox::indicator:checked {{
    background: {p.accent}; border-color: {p.accent}; image: url("{check}");
}}
QCheckBox::indicator:hover {{ border-color: {p.text_faint}; }}
QCheckBox:focus {{ color: {p.text}; }}

/* ---------------------------------------------------------- lists, trees, dialogs */
QDialog {{ background: {p.window}; }}
QDialog#Palette {{ background: {p.surface}; }}
QListView, QTreeView {{
    background: {p.surface_alt}; color: {p.text};
    border: 1px solid {p.border}; border-radius: {RADIUS_SM}px; padding: 4px;
    outline: none;
}}
QListView::item, QTreeView::item {{ padding: 5px 6px; border-radius: 5px; }}
QListView::item:hover, QTreeView::item:hover {{ background: {p.surface}; }}
QListView::item:selected, QTreeView::item:selected {{
    background: {p.accent_soft}; color: {p.accent};
}}
QLineEdit#PaletteSearch {{
    font-size: 17px; padding: 10px 14px; border-radius: {RADIUS}px;
    background: {p.surface_alt}; border: 1px solid {p.border_strong};
}}
QLineEdit#PaletteSearch:focus {{ border-color: {p.accent}; }}
QLabel#PaletteHint {{ padding-left: 4px; }}

/* ---------------------------------------------------------- tables */
QTableView {{
    background: {p.surface_alt}; alternate-background-color: {p.surface};
    border: 1px solid {p.border}; border-radius: {RADIUS_SM}px;
    gridline-color: {p.border}; selection-background-color: {p.selection};
    selection-color: {p.text};
}}
QTableView::item {{ padding: 4px 8px; border: none; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background: {p.surface}; color: {p.text_muted};
    border: none; border-bottom: 1px solid {p.border}; border-right: 1px solid {p.border};
    padding: 6px 8px; font-weight: 600; font-size: 12px;
}}
QHeaderView::section:last {{ border-right: none; }}
QTableCornerButton::section {{ background: {p.surface}; border: none; }}

/* ---------------------------------------------------------- progress */
QProgressBar {{
    background: {p.surface_alt}; border: none; border-radius: 3px;
    min-height: 6px; max-height: 6px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 3px; }}

/* ---------------------------------------------------------- scrolling */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.scrollbar}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.border_strong}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.scrollbar}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    background: none; border: none; height: 0px; width: 0px;
}}

/* ---------------------------------------------------------- log + dock */
QPlainTextEdit#LogView {{
    font-family: {MONO_FAMILY}; font-size: 12px; color: {p.text_muted};
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: {RADIUS_SM}px;
}}
QDockWidget {{ color: {p.text_muted}; titlebar-close-icon: none; titlebar-normal-icon: none; }}
QDockWidget::title {{
    background: {p.sidebar}; border-top: 1px solid {p.border}; padding: 6px 12px; text-align: left;
}}
QWidget#DockBody {{ background: {p.sidebar}; }}
QSplitter::handle {{ background: {p.border}; }}
QStatusBar {{ background: {p.sidebar}; border-top: 1px solid {p.border}; color: {p.text_muted}; }}
QMenu {{
    background: {p.surface}; border: 1px solid {p.border_strong}; border-radius: 8px; padding: 6px;
}}
QMenu::item {{ padding: 6px 14px; border-radius: 5px; }}
QMenu::item:selected {{ background: {p.accent_soft}; color: {p.accent}; }}
"""
