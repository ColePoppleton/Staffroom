"""The left rail: brand, tool list, and shell-level buttons."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from teaching_tools.core.plugin import ToolPlugin

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

    def __init__(self, plugins: tuple[ToolPlugin, ...], parent: QWidget | None = None) -> None:
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
        title = QLabel("Teaching Tools")
        title.setObjectName("Brand")
        sub = QLabel(f"{len(plugins)} tool{'s' if len(plugins) != 1 else ''} installed")
        sub.setObjectName("BrandSub")
        brand_layout.addWidget(title)
        brand_layout.addWidget(sub)
        layout.addWidget(brand)

        section = QLabel("TOOLS")
        section.setProperty("role", "faint")
        section.setContentsMargins(20, 6, 20, 2)
        layout.addWidget(section)

        self.list = QListWidget()
        self.list.setObjectName("ToolList")
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setSpacing(0)
        for plugin in plugins:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, plugin.name)
            item.setSizeHint(QSize(SIDEBAR_WIDTH - 16, 52))
            self.list.addItem(item)
            self.list.setItemWidget(item, ToolItem(plugin))
        self.list.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.list, 1)

        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 14)
        bottom_layout.setSpacing(2)
        self.log_button = QPushButton("Log")
        self.log_button.setObjectName("SidebarButton")
        self.log_button.setCheckable(True)
        self.log_button.toggled.connect(self.log_toggled.emit)
        self.theme_button = QPushButton("Toggle theme")
        self.theme_button.setObjectName("SidebarButton")
        self.theme_button.clicked.connect(self.theme_toggle_requested.emit)
        self.settings_button = QPushButton("Settings")
        self.settings_button.setObjectName("SidebarButton")
        self.settings_button.setCheckable(True)
        self.settings_button.clicked.connect(self._on_settings)
        for b in (self.log_button, self.theme_button, self.settings_button):
            bottom_layout.addWidget(b)
        layout.addWidget(bottom)

    def select(self, name: str) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == name:
                self.list.setCurrentItem(item)
                return

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
