"""The launcher window: sidebar on the left, a stack of tool panels (and the
settings page) on the right, a log drawer along the bottom."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from teaching_tools.core.config import Config, Theme
from teaching_tools.core.discovery import discover_plugins
from teaching_tools.core.library.model import IndexStats
from teaching_tools.core.library.service import LibraryService
from teaching_tools.core.log import get_logger
from teaching_tools.core.plugin import ToolPlugin
from teaching_tools.shell.library.page import LibraryPage
from teaching_tools.shell.library.picker import pick_resource
from teaching_tools.shell.log_drawer import LogDrawer
from teaching_tools.shell.settings_page import SettingsPage
from teaching_tools.shell.sidebar import Sidebar
from teaching_tools.shell.theme import stylesheet
from teaching_tools.shell.tool_panel import ToolPanel
from teaching_tools.shell.widgets import make_label

log = get_logger(__name__)


class WelcomePage(QWidget):
    def __init__(self, has_tools: bool) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.addStretch(1)
        layout.addWidget(make_label("Teaching Tools", "title"), 0, Qt.AlignmentFlag.AlignHCenter)
        text = (
            "Pick a tool from the sidebar to get started."
            if has_tools
            else "No tools installed yet. Create one with:  tt new <name>"
        )
        label = QLabel(text)
        label.setProperty("role", "subtitle")
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(2)


class MainWindow(QMainWindow):
    def __init__(
        self,
        config: Config,
        plugins: tuple[ToolPlugin, ...] | None = None,
        library: LibraryService | None = None,
        *,
        auto_index: bool = True,
    ) -> None:
        super().__init__()
        self.config = config
        self.plugins = plugins if plugins is not None else discover_plugins()
        self.panels: dict[str, ToolPanel] = {}
        self.library = library or LibraryService(
            Path(config.general.resources_root), picker=self._pick_resource
        )
        self.setWindowTitle("Teaching Tools")
        self.setMinimumSize(1040, 680)
        self.resize(1240, 780)

        root = QWidget()
        root.setObjectName("Root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = Sidebar(self.plugins)
        self.stack = QStackedWidget()
        self.welcome = WelcomePage(bool(self.plugins))
        self.settings = SettingsPage(config)
        self.library_page = LibraryPage(self.library, config)
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.settings)
        self.stack.addWidget(self.library_page)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        self.log_drawer = LogDrawer(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.log_drawer)

        self.sidebar.tool_selected.connect(self.show_tool)
        self.sidebar.settings_requested.connect(self.show_settings)
        self.sidebar.log_toggled.connect(self.log_drawer.setVisible)
        self.sidebar.theme_toggle_requested.connect(self.toggle_theme)
        self.settings.theme_changed.connect(self.apply_theme)
        self.settings.resources_root_changed.connect(self.set_resources_root)
        self.sidebar.mode_changed.connect(self._on_mode)
        res = self.sidebar.resources
        res.search_changed.connect(self._on_search)
        res.kind_changed.connect(self.library_page.set_kind)
        res.show_hidden_toggled.connect(self._on_show_hidden)
        res.resource_selected.connect(self._on_resource_selected)
        res.reindex_requested.connect(self.library_page.reindex)
        res.hidden.setChecked(config.general.show_hidden)
        self.library_page.indexed.connect(self._on_indexed)
        self.library_page.resource_shown.connect(res.select)
        self.refresh_resources()
        QShortcut(QKeySequence("Ctrl+L"), self, self.sidebar.log_button.toggle)
        QShortcut(QKeySequence("Ctrl+,"), self, self.sidebar.settings_button.click)

        self.apply_theme(config.general.theme)
        names = [p.name for p in self.plugins]
        initial = config.general.last_tool if config.general.last_tool in names else ""
        if not initial and names:
            initial = names[0]
        if initial:
            self.sidebar.select(initial)
        if config.general.sidebar_mode == "resources":
            self.sidebar.set_mode("resources")
        if auto_index and self.library.root_exists and self.library.count() == 0:
            self.library_page.reindex()

    # -- navigation ------------------------------------------------------
    def panel_for(self, name: str) -> ToolPanel:
        if name not in self.panels:
            plugin = next(p for p in self.plugins if p.name == name)
            panel = ToolPanel(plugin, self.config, resources=self.library)
            self.panels[name] = panel
            self.stack.addWidget(panel)
        return self.panels[name]

    def show_tool(self, name: str) -> None:
        panel = self.panel_for(name)
        self.stack.setCurrentWidget(panel)
        if self.config.general.last_tool != name:
            self.config.general.last_tool = name
            self.config.save()
        log.debug("showing %s", name)

    def show_settings(self) -> None:
        self.stack.setCurrentWidget(self.settings)

    # -- resources -------------------------------------------------------
    def _on_mode(self, mode: str) -> None:
        if self.config.general.sidebar_mode != mode:
            self.config.general.sidebar_mode = mode
            self.config.save()
        if mode == "resources":
            self.stack.setCurrentWidget(self.library_page)
        else:
            current = self.config.general.last_tool
            if current in self.panels or any(p.name == current for p in self.plugins):
                self.show_tool(current)
            else:
                self.stack.setCurrentWidget(self.welcome)

    def _on_search(self, text: str) -> None:
        self.library_page.set_query(text)
        self.stack.setCurrentWidget(self.library_page)

    def _on_show_hidden(self, show: bool) -> None:
        self.config.general.show_hidden = show
        self.config.save()
        self.library_page.set_show_hidden(show)
        self.refresh_resources()

    def _on_resource_selected(self, rel_path: str) -> None:
        self.stack.setCurrentWidget(self.library_page)
        self.library_page.show_resource(rel_path)

    def _on_indexed(self, stats: IndexStats) -> None:
        self.refresh_resources()
        self.sidebar.resources.set_indexing(False)

    def refresh_resources(self) -> None:
        resources = self.library.resources(include_hidden=self.config.general.show_hidden)
        status = f"{len(resources)} files" if resources else "Nothing indexed yet"
        if not self.library.root_exists:
            status = "Folder not found: set it in Settings"
        self.sidebar.resources.set_resources(resources, status)
        self.library_page.refresh_status()

    def set_resources_root(self, root: str) -> None:
        self.library.set_root(Path(root))
        self.refresh_resources()
        self.library_page.reindex(full=True)

    def _pick_resource(self, filter_ext: str | None) -> Path | None:
        return pick_resource(self.library, filter_ext, self)

    # -- theming ---------------------------------------------------------
    def apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if app is not None and isinstance(app, QApplication):
            app.setStyleSheet(stylesheet(_as_theme(theme)))
        self.sidebar.set_theme_label(theme)
        self.library_page.set_theme(theme)
        if self.settings.theme.currentText() != theme:
            self.settings.theme.blockSignals(True)
            self.settings.theme.setCurrentText(theme)
            self.settings.theme.blockSignals(False)
        if self.config.general.theme != theme:
            self.config.general.theme = _as_theme(theme)
            self.config.save()

    def toggle_theme(self) -> None:
        self.apply_theme("light" if self.config.general.theme == "dark" else "dark")


def _as_theme(value: str) -> Theme:
    return "light" if value == "light" else "dark"
