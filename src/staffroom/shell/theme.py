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

/* the Library page: results in the column, the file's title, tags, the use bar */
/* Tags ▾ beside the type filter (#111). On, it reads as ink, not accent:
   the accent is kept for selection, primary actions, links and focus. */
QPushButton#TagFilter {{
    color: {p.text_muted}; padding: 4px 9px; min-height: 18px; font-size: 12.5px;
}}
QPushButton#TagFilter::menu-indicator {{ image: none; width: 0px; }}
QPushButton#TagFilter:hover {{ color: {p.text}; }}
QPushButton#TagFilter[active="true"] {{
    color: {p.text}; background: {p.surface}; border-color: {p.text_faint}; font-weight: 600;
}}
QWidget#LibraryColumn QListWidget#ResultList {{
    background: transparent; border: none; padding: 2px 6px;
}}
QLabel[role="file-title"] {{
    font-family: {SERIF_FAMILY}; font-size: 24px; font-weight: 600; letter-spacing: -0.2px;
}}
QFrame#TagChip {{
    background: {p.surface_alt}; border: 1px solid {p.border_strong}; border-radius: 11px;
}}
QLabel#TagText {{ font-size: 12px; background: transparent; }}
QPushButton#TagRemove {{
    background: transparent; border: none; color: {p.text_faint}; font-size: 13px;
    padding: 0px 4px; min-height: 0px;
}}
QPushButton#TagRemove:hover {{ color: {p.text}; }}
QPushButton#TagAdd {{
    background: transparent; border: 1px dashed {p.border_strong}; border-radius: 11px;
    color: {p.text_muted}; font-size: 12px; padding: 2px 10px; min-height: 0px;
}}
QPushButton#TagAdd:hover {{ color: {p.text}; border-color: {p.text_faint}; }}
QLineEdit#TagInput {{ font-size: 12px; padding: 2px 8px; border-radius: 11px; }}
QPushButton#NoteLink {{
    background: transparent; border: none; color: {p.text_muted}; font-size: 12px;
    padding: 2px 4px; min-height: 0px;
}}
QPushButton#NoteLink:hover, QPushButton#NoteLink:checked {{ color: {p.text}; }}
QFrame#UseBar {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: {RADIUS}px;
}}
QFrame#OpenForClass[role="primary"] {{
    background: {p.surface_alt}; border: 1px solid {p.accent}; border-radius: {RADIUS_SM}px;
}}
QPushButton#OpenForClassButton[role="primary"] {{
    background: {p.accent}; color: {p.on_accent}; border: none; font-weight: 600;
    border-radius: 0px; border-top-left-radius: 6px; border-bottom-left-radius: 6px;
    padding: 7px 16px;
}}
QPushButton#OpenForClassButton[role="primary"]:hover {{ background: {p.accent_hover}; }}
QPushButton#OpenForClassButton:pressed {{ background: {p.accent_pressed}; }}
QLineEdit#LessonLabel {{
    background: transparent; border: none; border-radius: 0px; padding: 6px 10px;
}}
QLineEdit#LessonLabel:focus {{ border: none; }}
QPushButton#UseTool {{ font-size: 13px; font-weight: 600; padding: 6px 9px; }}
QLabel#UseStatus {{ font-size: 13px; }}
QFrame#ExternalCard {{
    background: {p.surface_alt}; border: 1px dashed {p.border_strong}; border-radius: {RADIUS_SM}px;
}}
QPlainTextEdit#CodeView {{
    font-family: {MONO_FAMILY}; font-size: 12.5px; color: {p.text};
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: {RADIUS_SM}px;
}}
/* Numbered code views (code sources, translations): gutter, lit line, syntax. */
CodeViewWidget {{
    qproperty-gutterColor: {p.text_faint};
    qproperty-keywordColor: {p.code_builtin}; qproperty-builtinColor: {p.code_name};
    qproperty-nameColor: {p.code_name}; qproperty-numberColor: {p.code_number};
    qproperty-stringColor: {p.code_string}; qproperty-commentColor: {p.text_faint};
}}
/* The lit line is a selection: the line the selected table row points at. */
CodeViewWidget[lit="true"] {{
    qproperty-markColor: {p.accent}; qproperty-lineColor: {p.accent_soft};
}}
CodeViewWidget#CodeView {{ padding: 4px 8px 4px 0px; }}
QPushButton#CodeChange::menu-indicator {{ image: none; width: 0px; }}
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

/* ---------------------------------------------------------- the page preview (paper is white
   in both themes: it is what the printer makes) */
PageCanvas {{
    border: none; background: transparent; qproperty-canvasColor: {p.surface_alt};
}}
QListView#PageRail {{
    background: transparent; border: none; padding: 0px;
    qproperty-paperColor: {p.paper}; qproperty-edgeColor: {p.border_strong};
    qproperty-textColor: {p.text}; qproperty-captionColor: {p.text_muted};
}}
/* the accent rings the page shown large: where you are */
QListView#PageRail[ring="current"] {{ qproperty-accentColor: {p.accent}; }}
QListView#PageRail::item, QListView#PageRail::item:hover, QListView#PageRail::item:selected {{
    background: transparent; padding: 0px;
}}
QLabel#PageNote {{
    background: {p.surface}; border: 1px solid {p.border_strong}; border-radius: {RADIUS_SM}px;
    padding: 10px 12px; color: {p.text};
}}

/* ---------------------------------------------------------- reports (stat tiles, charts, cards) */
QFrame#StatTile {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: {RADIUS}px;
}}
QLabel[role="stat-value"] {{
    font-size: 22px; font-weight: 700; letter-spacing: -0.3px; color: {p.text};
}}
/* The accent in a result marks only the call to action (marks: reteach first). */
QLabel[role="stat-value"][action="true"] {{ color: {p.accent}; }}
QFrame#ReportCard {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: {RADIUS}px;
}}
QFrame#ReportCard QTableView {{
    border: none; border-top: 1px solid {p.border}; border-radius: 0px;
}}
QWidget#FoldSection {{
    background: transparent; border: 1px dashed {p.border_strong}; border-radius: {RADIUS}px;
}}
QPushButton[role="disclosure"] {{
    background: transparent; border: none; color: {p.text_muted}; font-weight: 600;
    padding: 4px 0px; text-align: left;
}}
QPushButton[role="disclosure"]:hover {{ color: {p.text}; }}
BarCanvas {{
    qproperty-barColor: {p.text}; qproperty-textColor: {p.text};
    qproperty-mutedColor: {p.text_muted}; qproperty-faintColor: {p.text_faint};
    qproperty-axisColor: {p.border_strong};
}}
TableWidget {{
    qproperty-barColor: {p.text_muted}; qproperty-trackColor: {p.border};
    qproperty-textColor: {p.text};
}}
TableWidget[action="true"] {{ qproperty-actionColor: {p.accent}; }}
QLabel[role="note-ok"] {{ color: {p.text_muted}; font-size: 12px; }}
QLabel[role="note-warn"] {{ color: {p.text}; font-size: 12px; font-weight: 600; }}

/* ---------------------------------------------------------- compact inputs (chip, switch, grid) */
QFrame#FileChip {{
    background: {p.surface_alt}; border: 1px solid {p.border_strong}; border-radius: {RADIUS_SM}px;
}}
QLabel#FileBadge {{
    background: {p.surface}; color: {p.text_muted}; border: 1px solid {p.border};
    border-radius: 4px; font-size: 9px; font-weight: 700; padding: 1px 4px;
}}
QLabel#FileName {{ font-weight: 600; }}
QFrame#Segmented {{
    background: {p.surface_alt}; border: 1px solid {p.border_strong}; border-radius: {RADIUS_SM}px;
}}
QPushButton#Segment {{
    background: transparent; border: none; border-radius: 5px; padding: 4px 10px;
    color: {p.text_muted}; font-weight: 600; min-height: 16px;
}}
QPushButton#Segment:checked {{
    background: {p.surface}; color: {p.text}; border-bottom: 2px solid {p.accent};
}}
QPushButton#Segment:hover:!checked {{ color: {p.text}; }}
QFrame#GridCell {{
    background: {p.surface_alt}; border: 1px solid {p.border_strong}; border-radius: {RADIUS_SM}px;
}}
QLabel#GridLabel {{ font-weight: 700; }}
QLineEdit#GridValue {{
    background: transparent; border: none; border-radius: 0px; padding: 5px 6px 5px 2px;
}}
QLineEdit#GridValue:focus {{ border: none; border-bottom: 2px solid {p.accent}; }}

/* the result strip (top of the output pane) and the Details footer */
QWidget#ResultStrip {{ background: {p.surface}; border-bottom: 1px solid {p.border}; }}
QLabel#StripIcon {{
    border-radius: 10px; font-size: 12px; font-weight: 700;
    border: 1px solid {p.border_strong}; color: {p.text_faint}; background: transparent;
}}
QLabel#StripIcon[state="success"] {{
    background: {p.success}; border-color: {p.success}; color: {p.window};
}}
QLabel#StripIcon[state="danger"] {{
    background: {p.danger}; border-color: {p.danger}; color: {p.window};
}}
QLabel#StripHeadline {{ font-weight: 600; font-size: 14px; padding-top: 1px; }}
QLabel#StripMessage {{ font-size: 14px; padding-top: 1px; }}
QLabel#StripMessage[role="outcome"] {{ font-weight: 600; }}
QLabel#StripMessage[role="muted"] {{ color: {p.text_muted}; }}
QLabel#StripMessage[role="danger"] {{ color: {p.danger}; font-weight: 600; }}
QPushButton#ResultChip {{
    background: {p.surface_alt}; border: 1px solid {p.border_strong}; border-radius: 9px;
    padding: 0px; min-height: 0px;
}}
QPushButton#ResultChip:hover {{ border-color: {p.text_faint}; background: {p.surface}; }}
QPushButton#ResultChip:pressed {{ background: {p.selection}; }}
QLabel#ChipKind {{
    color: {p.text_muted}; font-size: 10px; font-weight: 700; letter-spacing: 0.3px;
    background: transparent;
}}
QLabel#ChipLabel {{ font-size: 12px; background: transparent; }}
QPushButton#WarningToggle {{
    background: transparent; border: none; color: {p.warning}; font-weight: 600;
    padding: 2px 4px; min-height: 0px;
}}
QPushButton#WarningToggle:hover {{ text-decoration: underline; }}
QLabel#WarningList {{ color: {p.warning}; padding-left: 30px; }}
QWidget#Details {{ background: {p.surface_alt}; }}
QWidget#DetailsBar {{ background: {p.surface}; border-top: 1px solid {p.border}; }}
QPushButton#DetailsToggle {{
    background: transparent; border: none; color: {p.text_muted}; font-weight: 600;
    font-size: 12px; padding: 0px; min-height: 0px;
}}
QPushButton#DetailsToggle:hover {{ color: {p.text}; }}

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
