"""The left rail: brand, tool list, and shell-level buttons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.plugin import ToolPlugin
from staffroom.shell.library.sidebar_panel import ResourcesPanel

SIDEBAR_WIDTH = 248


class ToolItem(QWidget):
    def __init__(self, plugin: ToolPlugin) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        badge = QLabel(plugin.name[:1].upper())
        badge.setObjectName("ToolBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QVBoxLayout()
        text.setSpacing(1)
        name = QLabel(plugin.panel_spec().title or plugin.name)
        name.setObjectName("ToolName")
        desc = QLabel(_elide(plugin.description, 34))
        desc.setObjectName("ToolDesc")
        desc.setToolTip(plugin.description)
        text.addWidget(name)
        text.addWidget(desc)
        layout.addWidget(badge)
        layout.addLayout(text, 1)


def _elide(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


class Sidebar(QWidget):
    tool_selected = Signal(str)
    settings_requested = Signal()
    log_toggled = Signal(bool)
    theme_toggle_requested = Signal()
    mode_changed = Signal(str)  # "tools" | "resources"

    def __init__(self, plugins: tuple[ToolPlugin, ...], parent: QWidget | None = None) -> None:
        """``plugins`` is what the list shows, in order: the host passes the
        visible ones only (``discovery.visible_plugins``)."""
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QWidget()
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(20, 22, 20, 14)
        brand_layout.setSpacing(2)
        title = QLabel("Staffroom")
        title.setObjectName("Brand")
        sub = QLabel(f"{len(plugins)} tool{'s' if len(plugins) != 1 else ''} installed")
        sub.setObjectName("BrandSub")
        brand_layout.addWidget(title)
        brand_layout.addWidget(sub)
        layout.addWidget(brand)

        tabs = QWidget()
        tabs.setObjectName("SidebarTabs")
        tabs_layout = QHBoxLayout(tabs)
        tabs_layout.setContentsMargins(3, 3, 3, 3)
        tabs_layout.setSpacing(2)
        self.tools_tab = QPushButton("Tools")
        self.resources_tab = QPushButton("Resources")
        self.tab_group = QButtonGroup(self)
        for i, b in enumerate((self.tools_tab, self.resources_tab)):
            b.setObjectName("SidebarTab")
            b.setCheckable(True)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.tab_group.addButton(b, i)
            tabs_layout.addWidget(b, 1)
        self.tools_tab.setChecked(True)
        self.tab_group.idClicked.connect(self._on_tab)
        tabs_wrap = QWidget()
        wrap_layout = QVBoxLayout(tabs_wrap)
        wrap_layout.setContentsMargins(12, 0, 12, 8)
        wrap_layout.addWidget(tabs)
        layout.addWidget(tabs_wrap)

        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)

        tools_page = QWidget()
        tools_layout = QVBoxLayout(tools_page)
        tools_layout.setContentsMargins(0, 0, 0, 0)
        tools_layout.setSpacing(0)
        section = QLabel("TOOLS")
        section.setProperty("role", "faint")
        section.setContentsMargins(20, 6, 20, 2)
        tools_layout.addWidget(section)

        self.list = QListWidget()
        self.list.setObjectName("ToolList")
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setSpacing(0)
        for n, plugin in enumerate(plugins, 1):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, plugin.name)
            if n <= 9:
                item.setToolTip(f"{plugin.description}  (⌘{n})")
            item.setSizeHint(QSize(SIDEBAR_WIDTH - 16, 52))
            self.list.addItem(item)
            self.list.setItemWidget(item, ToolItem(plugin))
        self.list.currentItemChanged.connect(self._on_current_changed)
        tools_layout.addWidget(self.list, 1)
        self.pages.addWidget(tools_page)

        self.resources = ResourcesPanel()
        self.pages.addWidget(self.resources)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 14)
        bottom_layout.setSpacing(2)
        self.log_button = QPushButton("Log")
        self.log_button.setObjectName("SidebarButton")
        self.log_button.setToolTip("Show the log drawer  (⌘L)")
        self.log_button.setCheckable(True)
        self.log_button.toggled.connect(self.log_toggled.emit)
        self.theme_button = QPushButton("Toggle theme")
        self.theme_button.setObjectName("SidebarButton")
        self.theme_button.clicked.connect(self.theme_toggle_requested.emit)
        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("SidebarButton")
        self.settings_button.setToolTip("Settings  (⌘,)")
        self.update_button = QPushButton("Update available")
        self.update_button.setObjectName("SidebarButton")
        self.update_button.setProperty("role", "accent")
        self.update_button.setToolTip(
            "A newer version is on the git remote. Open Settings to update."
        )
        self.update_button.clicked.connect(self._on_settings)
        self.update_button.hide()
        self.settings_button.setCheckable(True)
        self.settings_button.clicked.connect(self._on_settings)
        for b in (self.update_button, self.log_button, self.theme_button, self.settings_button):
            bottom_layout.addWidget(b)
        layout.addWidget(bottom)

    def select(self, name: str) -> bool:
        """Make ``name`` current. False when it is not listed (a hidden tool)."""
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == name:
                self.list.setCurrentItem(item)
                return True
        return False

    def tool_names(self) -> list[str]:
        """The listed tools, top to bottom (the ⌘1-⌘9 order)."""
        return [
            str(self.list.item(i).data(Qt.ItemDataRole.UserRole)) for i in range(self.list.count())
        ]

    def mode(self) -> str:
        return "resources" if self.resources_tab.isChecked() else "tools"

    def set_mode(self, mode: str) -> None:
        button = self.resources_tab if mode == "resources" else self.tools_tab
        if not button.isChecked():
            button.setChecked(True)
        self._on_tab(self.tab_group.id(button))

    def _on_tab(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        self.settings_button.setChecked(False)
        self.mode_changed.emit("resources" if index == 1 else "tools")

    def set_update_available(self, available: bool) -> None:
        self.update_button.setVisible(available)

    def set_theme_label(self, theme: str) -> None:
        self.theme_button.setText("Light theme" if theme == "dark" else "Dark theme")

    def _on_current_changed(self, current: QListWidgetItem | None) -> None:
        if current is not None:
            self.settings_button.setChecked(False)
            self.tool_selected.emit(current.data(Qt.ItemDataRole.UserRole))

    def _on_settings(self) -> None:
        self.settings_button.setChecked(True)
        self.list.clearSelection()
        self.list.setCurrentRow(-1)
        self.settings_requested.emit()
