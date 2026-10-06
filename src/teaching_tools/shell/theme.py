"""Design tokens and the generated Qt stylesheet.

One :class:`Palette` per theme; :func:`stylesheet` turns it into QSS. Widgets
opt into roles with object names (``#Sidebar``, ``#Card``) and dynamic
properties (``role="primary"``, ``role="muted"``) so the kit stays free of
hard-coded colours.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from teaching_tools.core.config import Theme


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

FONT_FAMILY = '-apple-system, "SF Pro Text", "Helvetica Neue", "Segoe UI", sans-serif'
MONO_FAMILY = '"SF Mono", Menlo, Consolas, monospace'
RADIUS = 10
RADIUS_SM = 7
ASSETS = Path(__file__).with_name("assets")


def asset(name: str) -> str:
    return ASSETS.joinpath(name).as_posix()


def palette(theme: Theme) -> Palette:
    return PALETTES.get(theme, DARK)


def stylesheet(theme: Theme) -> str:
    p = palette(theme)
    check = asset("check.svg")
    chevron = asset(f"chevron-{'light' if theme == 'light' else 'dark'}.svg")
    chevron_right = asset(f"chevron-right-{'light' if theme == 'light' else 'dark'}.svg")
    return f"""
* {{
    font-family: {FONT_FAMILY};
    font-size: 13px;
    color: {p.text};
    outline: none;
}}
QMainWindow, QWidget#Root {{ background: {p.window}; }}
QToolTip {{
    background: {p.surface}; color: {p.text};
    border: 1px solid {p.border_strong}; border-radius: 6px; padding: 6px 8px;
}}

/* ---------------------------------------------------------- typography */
QLabel[role="title"] {{ font-size: 22px; font-weight: 600; letter-spacing: -0.2px; }}
QLabel[role="subtitle"] {{ font-size: 13px; color: {p.text_muted}; }}
QLabel[role="section"] {{ font-size: 13px; font-weight: 600; color: {p.text}; }}
QLabel[role="muted"] {{ color: {p.text_muted}; }}
QLabel[role="faint"] {{ color: {p.text_faint}; font-size: 12px; }}
QLabel[role="chip"] {{
    background: {p.accent_soft}; color: {p.accent};
    border-radius: 9px; padding: 1px 8px; font-size: 11px; font-weight: 600;
}}
QLabel[role="danger"] {{ color: {p.danger}; }}
QLabel[role="success"] {{ color: {p.success}; }}
QLabel[role="empty"] {{
    color: {p.text_faint}; font-size: 13px;
    border: 1px dashed {p.border_strong}; border-radius: {RADIUS_SM}px; padding: 28px;
}}

/* ---------------------------------------------------------- sidebar */
QWidget#Sidebar {{
    background: {p.sidebar};
    border-right: 1px solid {p.border};
}}
QLabel#Brand {{ font-size: 15px; font-weight: 700; letter-spacing: -0.2px; }}
QLabel#BrandSub {{ font-size: 11px; color: {p.text_faint}; }}
QListWidget#ToolList {{
    background: transparent; border: none; padding: 4px 8px;
}}
QListWidget#ToolList::item {{
    border-radius: {RADIUS_SM}px; padding: 0px; margin: 2px 0px;
}}
QListWidget#ToolList::item:hover {{ background: {p.surface}; }}
QListWidget#ToolList::item:selected {{ background: {p.accent_soft}; }}
QLabel#ToolBadge {{
    background: {p.surface_alt}; color: {p.text_muted};
    border: 1px solid {p.border}; border-radius: 8px;
    font-weight: 700; font-size: 13px;
    min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px;
}}
QListWidget#ToolList::item:selected QLabel#ToolBadge {{
    background: {p.accent}; color: {p.on_accent}; border-color: {p.accent};
}}
QLabel#ToolName {{ font-weight: 600; }}
QLabel#ToolDesc {{ color: {p.text_muted}; font-size: 11px; }}
QPushButton#SidebarButton {{
    background: transparent; border: none; border-radius: {RADIUS_SM}px;
    padding: 7px 10px; text-align: left; color: {p.text_muted};
}}
QPushButton#SidebarButton:hover {{ background: {p.surface}; color: {p.text}; }}
QPushButton#SidebarButton:checked {{ background: {p.accent_soft}; color: {p.accent}; }}
QWidget#SidebarTabs {{
    background: {p.surface_alt}; border: 1px solid {p.border}; border-radius: {RADIUS_SM}px;
}}
QPushButton#SidebarTab {{
    background: transparent; border: none; border-radius: 5px; padding: 5px 10px;
    color: {p.text_muted}; font-weight: 600;
}}
QPushButton#SidebarTab:checked {{ background: {p.surface}; color: {p.text}; }}
QPushButton#SidebarTab:hover:!checked {{ color: {p.text}; }}
QTreeView#ResourceTree {{
    background: transparent; border: none; padding: 2px 0px;
    show-decoration-selected: 0;
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
QListWidget#ResultList {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: {RADIUS}px; padding: 6px;
}}
QListWidget#ResultList::item {{ border-radius: {RADIUS_SM}px; margin: 2px 0px; }}
QListWidget#ResultList::item:hover {{ background: {p.surface_alt}; }}
QListWidget#ResultList::item:selected {{ background: {p.accent_soft}; }}
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
QWidget#Header {{ background: transparent; }}
QWidget#Footer {{ background: {p.sidebar}; border-top: 1px solid {p.border}; }}

/* ---------------------------------------------------------- buttons */
QPushButton {{
    background: {p.surface_alt}; color: {p.text};
    border: 1px solid {p.border_strong}; border-radius: {RADIUS_SM}px;
    padding: 6px 14px; min-height: 18px;
}}
QPushButton:hover {{ border-color: {p.accent}; }}
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
    background: {p.accent_soft}; color: {p.text_faint}; border-color: {p.accent_soft};
}}
QPushButton[role="ghost"] {{
    background: transparent; border: 1px solid transparent; color: {p.text_muted}; padding: 4px 8px;
}}
QPushButton[role="ghost"]:hover {{ color: {p.accent}; background: {p.accent_soft}; }}
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
QCheckBox::indicator:hover {{ border-color: {p.accent}; }}

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
