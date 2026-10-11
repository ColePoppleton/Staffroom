"""The left rail: the brand row, a library search field, the destinations
grouped by the teacher's week, and a footer with the version and the log.

Destinations are the Library (the shell's own, first in *Lessons*) and every
visible tool, grouped by the plugin's ``group`` and drawn with its ``glyph``
(both plain data on the plugin, see ``core.plugin``). One line per tool; the
description lives in the tooltip. The accent marks only the current
destination, so the one red thing on a tool's page is its primary action.

The sidebar never decides what the window shows: it emits a request and the
window calls :meth:`Sidebar.set_current` with whatever it ended up showing,
so the highlight always matches the page (``--settings`` included).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from staffroom import __version__
from staffroom.core.config import Theme
from staffroom.core.discovery import grouped
from staffroom.core.plugin import GROUPS, ToolPlugin, plugin_glyph
from staffroom.shell.theme import asset, glyph_icon, glyph_pixmap, palette

SIDEBAR_WIDTH = 232
LIBRARY = "@library"
"""The Library's key among the destinations (no tool can be called this)."""
SETTINGS = "@settings"
LIBRARY_GROUP = GROUPS[0]  # the Library opens "Lessons", above Classroom
LIBRARY_GLYPH = "books"
LIBRARY_TIP = "Your resources folder: search, preview, open for class  (⌘K)"
GLYPH_SIZE = 13


def _repolish(*widgets: QWidget) -> None:
    for widget in widgets:
        widget.style().unpolish(widget)
        widget.style().polish(widget)


class NavItem(QFrame):
    """One destination: a glyph in a small box, the name, an optional count.
    A click (or Space / Return when it has focus) emits ``activated``."""

    activated = Signal(str)

    def __init__(self, key: str, title: str, glyph: str, tooltip: str = "") -> None:
        super().__init__()
        self.key = key
        self.glyph_name = glyph
        self.theme: Theme = "dark"
        self.current = False
        self.setObjectName("NavItem")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        # Like the rest of the rail, out of the tab chain: the keyboard route
        # is ⌘1-⌘9, ⌘K and ⌘, (and the row still answers Space / Return).
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setAccessibleName(title)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 5, 8, 5)
        layout.setSpacing(10)
        self.glyph = QLabel()
        self.glyph.setObjectName("NavGlyph")
        self.glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label = QLabel(title)
        self.label.setObjectName("NavText")
        # A long third-party title clips at the row's edge instead of
        # widening the fixed-width sidebar; the tooltip has the rest.
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.count = QLabel("")
        self.count.setObjectName("NavCount")
        self.count.hide()
        layout.addWidget(self.glyph)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.count)
        self._paint_glyph()

    def title(self) -> str:
        return self.label.text()

    def set_current(self, current: bool) -> None:
        if current == self.current:
            return
        self.current = current
        for widget in (self, self.glyph):
            widget.setProperty("current", current)
        _repolish(self, self.glyph)
        self._paint_glyph()

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self._paint_glyph()

    def set_count(self, text: str) -> None:
        self.count.setText(text)
        self.count.setVisible(bool(text))

    def glyph_color(self) -> str:
        p = palette(self.theme)
        return p.accent if self.current else p.text_muted

    def _paint_glyph(self) -> None:
        self.glyph.setPixmap(glyph_pixmap(self.glyph_name, self.glyph_color(), GLYPH_SIZE))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.activated.emit(self.key)
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activated.emit(self.key)
            return
        super().keyPressEvent(event)


class NavRow(QWidget):
    """A :class:`NavItem` with the accent bar at the sidebar's left edge."""

    def __init__(self, item: NavItem) -> None:
        super().__init__()
        self.item = item
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 1, 12, 1)
        layout.setSpacing(9)
        self.bar = QFrame()
        self.bar.setObjectName("NavBar")
        self.bar.setFixedWidth(3)
        layout.addWidget(self.bar)
        layout.addWidget(item, 1)

    def set_current(self, current: bool) -> None:
        self.item.set_current(current)
        self.bar.setProperty("current", current)
        _repolish(self.bar)


class SearchField(QLineEdit):
    """The library search in the sidebar: a field with a ``⌘K`` hint inside
    its right edge. Typing hands the text to the Library's own search box."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SidebarSearch")
        self.setPlaceholderText("Search resources")
        self.setToolTip("Search the library by name and text  (⌘K)")
        self.setAccessibleName("Search resources")
        # Clicked into, never handed focus when the window opens.
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.kbd = QLabel("⌘K", self)
        self.kbd.setObjectName("Kbd")
        self.kbd.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._search_action = self.addAction(QPixmap(), QLineEdit.ActionPosition.LeadingPosition)

    def set_theme(self, theme: Theme) -> None:
        self._search_action.setIcon(glyph_icon("search", palette(theme).text_muted, 13))

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.kbd.adjustSize()
        self.kbd.move(self.width() - self.kbd.width() - 8, (self.height() - self.kbd.height()) // 2)


class Sidebar(QWidget):
    tool_selected = Signal(str)
    library_requested = Signal()
    settings_requested = Signal()
    updates_requested = Signal()  # the footer's update link: Settings > Updates
    search_requested = Signal(str)
    log_toggled = Signal(bool)

    def __init__(self, plugins: tuple[ToolPlugin, ...], parent: QWidget | None = None) -> None:
        """``plugins`` is what the list shows: the host passes the visible
        ones only (``discovery.visible_plugins``). They are listed by group
        (``discovery.grouped``), which is also the ``⌘1``-``⌘9`` order."""
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFixedWidth(SIDEBAR_WIDTH)
        self.theme: Theme = "dark"
        self._current = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 10)
        layout.setSpacing(0)
        layout.addWidget(self._build_brand())

        search_wrap = QWidget()
        search_layout = QVBoxLayout(search_wrap)
        search_layout.setContentsMargins(12, 0, 12, 6)
        self.search = SearchField()
        self.search.textEdited.connect(self._on_search_edited)
        self.search.returnPressed.connect(lambda: self._on_search_edited(self.search.text()))
        search_layout.addWidget(self.search)
        layout.addWidget(search_wrap)

        self.rows: dict[str, NavRow] = {}
        self._tool_order: list[str] = []
        self.group_labels: list[QLabel] = []
        layout.addWidget(self._build_nav(plugins), 1)
        layout.addLayout(self._build_footer())
        self.set_theme("dark")

    # -- building -------------------------------------------------------
    def _build_brand(self) -> QWidget:
        """The mark, *Staffroom* in Fraunces, and the settings gear."""
        brand = QWidget()
        row = QHBoxLayout(brand)
        row.setContentsMargins(16, 0, 14, 12)
        row.setSpacing(9)
        mark = QLabel()
        mark.setObjectName("BrandMark")
        mark.setFixedSize(26, 26)
        pixmap = QPixmap(asset("mark.svg"))
        if not pixmap.isNull():
            ratio = 2.0
            side = round(26 * ratio)
            pixmap = pixmap.scaled(
                QSize(side, side),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            pixmap.setDevicePixelRatio(ratio)
            mark.setPixmap(pixmap)
        title = QLabel("Staffroom")
        title.setObjectName("Brand")
        self.settings_button = QToolButton()
        self.settings_button.setObjectName("BrandGear")
        self.settings_button.setCheckable(True)
        self.settings_button.setToolTip("Settings  (⌘,)")
        self.settings_button.setAccessibleName("Settings")
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setIconSize(QSize(14, 14))
        self.settings_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.settings_button.clicked.connect(self._on_settings_clicked)
        row.addWidget(mark)
        row.addWidget(title, 1)
        row.addWidget(self.settings_button)
        return brand

    def _build_nav(self, plugins: tuple[ToolPlugin, ...]) -> QScrollArea:
        """One header per group, one line per destination, scrolling only
        when a teacher has added more tools than the window is tall."""
        body = QWidget()
        body.setObjectName("NavBody")
        nav = QVBoxLayout(body)
        nav.setContentsMargins(0, 0, 0, 8)
        nav.setSpacing(0)
        groups = grouped(plugins)
        if not any(name == LIBRARY_GROUP for name, _ in groups):
            groups.insert(0, (LIBRARY_GROUP, ()))
        for group, tools in groups:
            label = QLabel(group.upper())
            label.setObjectName("NavGroup")
            label.setAccessibleName(group)
            self.group_labels.append(label)
            nav.addWidget(label)
            if group == LIBRARY_GROUP:
                nav.addWidget(self._add_row(LIBRARY, "Library", LIBRARY_GLYPH, LIBRARY_TIP))
            for plugin in tools:
                self._tool_order.append(plugin.name)
                n = len(self._tool_order)
                tip = plugin.description + (f"  (⌘{n})" if n <= 9 else "")
                title = plugin.panel_spec().title or plugin.name
                nav.addWidget(self._add_row(plugin.name, title, plugin_glyph(plugin), tip))
        nav.addStretch(1)
        scroll = QScrollArea()
        scroll.setObjectName("NavScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(body)
        return scroll

    def _build_footer(self) -> QVBoxLayout:
        """The running version and update state, and the activity log."""
        footer = QWidget()
        footer.setObjectName("SidebarFooter")
        footer.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        row = QHBoxLayout(footer)
        row.setContentsMargins(8, 9, 2, 0)
        row.setSpacing(6)
        # The running version, so "am I on the latest release?" has an answer
        # in the window (#69); Settings > Updates adds the branch and commit.
        self.version_label = QLabel(f"v{__version__}")
        self.version_label.setObjectName("SidebarVersion")
        self.version_label.setToolTip(
            f"Staffroom {__version__}. Settings › Updates has the details."
        )
        self.update_button = QPushButton("update")
        self.update_button.setObjectName("FooterLink")
        self.update_button.setProperty("role", "link")
        self.update_button.setToolTip("A newer release is out. Settings › Updates installs it.")
        self.update_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_button.clicked.connect(self._on_updates_clicked)
        self.update_button.hide()
        self.update_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.log_button = QPushButton("Activity log")
        self.log_button.setObjectName("FooterLink")
        self.log_button.setCheckable(True)
        self.log_button.setToolTip("Show the activity log  (⌘L)")
        self.log_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.log_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.log_button.toggled.connect(self.log_toggled.emit)
        row.addWidget(self.version_label)
        row.addWidget(self.update_button)
        row.addStretch(1)
        row.addWidget(self.log_button)
        wrap = QVBoxLayout()
        wrap.setContentsMargins(12, 0, 12, 0)
        wrap.addWidget(footer)
        return wrap

    def _add_row(self, key: str, title: str, glyph: str, tooltip: str) -> NavRow:
        item = NavItem(key, title, glyph, tooltip)
        item.activated.connect(self._on_activated)
        row = NavRow(item)
        self.rows[key] = row
        return row

    # -- state the window sets ------------------------------------------
    def set_current(self, key: str) -> None:
        """Highlight ``key`` (a tool name, :data:`LIBRARY` or :data:`SETTINGS`)
        and nothing else; ``""`` or an unlisted tool highlights nothing.
        Emits nothing: the window calls this with what it now shows."""
        self._current = key
        for name, row in self.rows.items():
            row.set_current(name == key)
        self.settings_button.setChecked(key == SETTINGS)
        self._paint_gear()

    def current(self) -> str:
        return self._current

    def select(self, name: str) -> bool:
        """Choose the listed tool ``name`` as a click would (emits
        ``tool_selected``). False when it is not listed (a hidden tool)."""
        if name not in self._tool_order:
            return False
        self.tool_selected.emit(name)
        return True

    def tool_names(self) -> list[str]:
        """The listed tools, top to bottom: the ``⌘1``-``⌘9`` order."""
        return list(self._tool_order)

    def item(self, key: str) -> NavItem | None:
        row = self.rows.get(key)
        return row.item if row is not None else None

    def set_library_count(self, text: str) -> None:
        """The number beside *Library* (files in the index), or ``""``."""
        self.rows[LIBRARY].item.set_count(text)

    def set_update_available(self, available: bool | None, label: str = "update") -> None:
        """``None`` until a check answers and when it failed: just the
        version. Then *up to date*, or a link that opens Settings > Updates:
        *update* for a checkout, *0.9.0 out* for an installed copy (#11)."""
        shown = bool(available)
        self.update_button.setVisible(shown)
        if shown:
            self.update_button.setText(label or "update")
            self.update_button.setToolTip(
                "A newer release is out. Settings › Updates installs it."
                if (label or "update") == "update"
                else f"Staffroom {label.removesuffix(' out')} is out. "
                "Settings › Updates has the one command that updates."
            )
        state = {None: "", False: " · up to date", True: " ·"}[available]
        self.version_label.setText(f"v{__version__}{state}")

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        for row in self.rows.values():
            row.item.set_theme(theme)
        self.search.set_theme(theme)
        self._paint_gear()

    # -- requests -------------------------------------------------------
    def _paint_gear(self) -> None:
        p = palette(self.theme)
        color = p.accent if self.settings_button.isChecked() else p.text_muted
        self.settings_button.setIcon(glyph_icon("gear", color, 14))

    def _on_activated(self, key: str) -> None:
        if key == LIBRARY:
            self.library_requested.emit()
        else:
            self.tool_selected.emit(key)

    def _on_settings_clicked(self) -> None:
        # Undo the button's own toggle: only set_current decides its state.
        self.settings_button.setChecked(self._current == SETTINGS)
        self.settings_requested.emit()

    def _on_updates_clicked(self) -> None:
        self.updates_requested.emit()

    def _on_search_edited(self, text: str) -> None:
        if text:
            self.search_requested.emit(text)
