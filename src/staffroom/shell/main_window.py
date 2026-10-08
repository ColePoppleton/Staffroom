"""The launcher window: sidebar on the left, a stack of tool panels (and the
settings page) on the right, a log drawer along the bottom."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from staffroom.core import paths
from staffroom.core.config import Config, Theme
from staffroom.core.discovery import discover_plugins, visible_plugins
from staffroom.core.library.model import IndexStats, withheld_message
from staffroom.core.library.service import LibraryService
from staffroom.core.log import get_logger
from staffroom.core.plugin import ToolPlugin
from staffroom.shell.library.page import LibraryPage
from staffroom.shell.library.picker import pick_resource
from staffroom.shell.log_drawer import LogDrawer
from staffroom.shell.settings_page import SettingsPage
from staffroom.shell.sidebar import Sidebar
from staffroom.shell.theme import stylesheet
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets import FirstRunCard, make_label

log = get_logger(__name__)


class WelcomePage(QWidget):
    def __init__(self, has_tools: bool) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.addStretch(1)
        layout.addWidget(make_label("Staffroom", "title"), 0, Qt.AlignmentFlag.AlignHCenter)
        text = (
            "Pick a tool from the sidebar to get started."
            if has_tools
            else "No tools installed yet. Create one with:  staff new <name>"
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
        first_run: bool | None = None,
    ) -> None:
        """``first_run`` forces the welcome card on or off; None (the default)
        shows it exactly when no resources folder is set."""
        super().__init__()
        self.config = config
        # Every loadable tool; hidden ones can still be opened by name
        # (``staffroom --tool hello``) but are not listed or on a shortcut.
        self.plugins = plugins if plugins is not None else discover_plugins()
        self.visible_plugins = visible_plugins(self.plugins)
        self.panels: dict[str, ToolPanel] = {}
        self.library = library or LibraryService(
            Path(config.general.resources_root),
            picker=self._pick_resource,
            exclude=config.general.library_exclude,
        )
        self.setWindowTitle("Staffroom")
        self.setMinimumSize(1040, 680)
        self.resize(1240, 780)

        root = QWidget()
        root.setObjectName("Root")
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.sidebar = Sidebar(self.visible_plugins)
        self.stack = QStackedWidget()
        self.welcome = WelcomePage(bool(self.visible_plugins))
        self.settings = SettingsPage(config)
        self.library_page = LibraryPage(self.library, config)
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.settings)
        self.stack.addWidget(self.library_page)
        # The one-card welcome of a fresh install. None once a folder is set.
        show_card = not config.general.resources_root if first_run is None else first_run
        self.first_run: FirstRunCard | None = None
        self._first_run_target = ""
        self._first_run_pending = show_card
        if show_card:
            # The default is shown as written (~/TeachingSessions), not expanded.
            sessions = config.general.sessions_root or paths.DEFAULT_SESSIONS_ROOT
            self.first_run = FirstRunCard(sessions)
            self.first_run.folder_chosen.connect(self._on_first_run_folder)
            self.first_run.dismissed.connect(self.finish_first_run)
            self.stack.addWidget(self.first_run)
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
        self.settings.library_exclude_changed.connect(self.set_library_exclude)
        self.settings.update_available.connect(self.sidebar.set_update_available)
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
        QShortcut(QKeySequence("Ctrl+K"), self, self.focus_library_search)
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_for_class)
        # ⌘1-⌘9 follow the sidebar top to bottom, so they skip hidden tools.
        for n, plugin in enumerate(self.visible_plugins[:9], 1):
            QShortcut(
                QKeySequence(f"Ctrl+{n}"), self, lambda name=plugin.name: self.go_to_tool(name)
            )

        self.apply_theme(config.general.theme)
        names = [p.name for p in self.visible_plugins]
        initial = config.general.last_tool if config.general.last_tool in names else ""
        if not initial and names:
            initial = names[0]  # a fresh config opens on the first workflow tool
        if self.first_run is not None:
            # The card comes first; Choose… or Not now then lands on ``initial``.
            self._first_run_target = initial
            self.stack.setCurrentWidget(self.first_run)
        elif initial:
            self.sidebar.select(initial)
        if config.general.sidebar_mode == "resources" and self.first_run is None:
            self.sidebar.set_mode("resources")
        # A folder that was never fully indexed: empty, or an index that was
        # stopped early (closing the window mid-index keeps the files done so
        # far but stamps no ``last_indexed``) finishes now.
        if auto_index and self.library.root_exists and self.library.last_indexed() is None:
            self.library_page.reindex()
        if auto_index and not config.read_only:
            self.settings.check_updates(fetch=True)

    # -- lifetime --------------------------------------------------------
    def wait_for_workers(self, timeout_ms: int = 10_000) -> bool:
        """Stop the index worker (at its next file) and wait for it and for
        any tool run still going, so no ``QThread`` is destroyed while it
        runs: Qt aborts the whole process for that (#40). The window calls
        this when it closes; screenshot runs and test fixtures call it before
        tearing the window down. Returns True when every worker has stopped."""
        stopped = self.library_page.stop_index(timeout_ms)
        for panel in self.panels.values():
            worker = panel.worker
            if worker is not None and worker.isRunning() and not worker.wait(timeout_ms):
                log.error("%s worker did not stop within %d ms", panel.plugin.name, timeout_ms)
                stopped = False
        return stopped

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.wait_for_workers()
        super().closeEvent(event)

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

    # -- first run -------------------------------------------------------
    def _on_first_run_folder(self, root: str) -> None:
        """The card's folder goes through the Settings picker, so saving, the
        library root and the full first index follow the one existing path;
        the card then shows that index's progress until it lands on a tool."""
        self.settings.resources_root.set_path(Path(root))
        worker = self.library_page.worker
        if self.first_run is not None and worker is not None and worker.isRunning():
            worker.progress.connect(self.first_run.show_progress)
        else:
            self.finish_first_run()  # nothing to wait for (same folder, or no index)

    def finish_first_run(self) -> None:
        """Leave the card for the first workflow tool. Runs once: the index
        finishing and "Continue" / "Not now" may both get here."""
        if not self._first_run_pending:
            return
        self._first_run_pending = False
        if self._first_run_target:
            self.go_to_tool(self._first_run_target)
        else:
            self.stack.setCurrentWidget(self.welcome)

    # -- shortcuts -------------------------------------------------------
    def focus_library_search(self) -> None:
        """⌘K: jump to the Resources search box."""
        self.sidebar.set_mode("resources")
        self.stack.setCurrentWidget(self.library_page)
        self.sidebar.resources.search.setFocus()
        self.sidebar.resources.search.selectAll()

    def go_to_tool(self, name: str) -> None:
        """Show ``name``: through the sidebar when it is listed, directly when
        it is a hidden tool (``staffroom --tool hello``). Unknown names do nothing."""
        self.sidebar.set_mode("tools")
        if self.sidebar.select(name):
            return
        if any(p.name == name for p in self.plugins):
            self.sidebar.list.clearSelection()
            self.sidebar.list.setCurrentRow(-1)
            self.show_tool(name)

    def open_for_class(self) -> None:
        """⌘O: the classroom tool with the library picker open, when installed."""
        if not any(p.name == "classroom" for p in self.plugins):
            return
        self.go_to_tool("classroom")
        panel = self.panel_for("classroom")
        picker = panel.resource_pickers.get("resource")
        if picker is not None:
            picker.pick_from_library()

    # -- resources -------------------------------------------------------
    def _on_mode(self, mode: str) -> None:
        if self.config.general.sidebar_mode != mode:
            self.config.general.sidebar_mode = mode
            self.config.save()
        if mode == "resources":
            self.stack.setCurrentWidget(self.library_page)
        else:
            current = self.config.general.last_tool
            if self._first_run_pending and self.first_run is not None:
                self.stack.setCurrentWidget(self.first_run)
            elif current in self.panels or any(p.name == current for p in self.plugins):
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
        if self.first_run is not None and self._first_run_pending:
            self.first_run.finish_indexing(stats.summary())
            self.finish_first_run()

    def refresh_resources(self) -> None:
        resources = self.library.resources(include_hidden=self.config.general.show_hidden)
        status = f"{len(resources)} files" if resources else "Nothing indexed yet"
        detail = ""
        withheld = self.library.withheld_count() if resources else 0
        if withheld:
            status += f"  ·  {withheld} name only"
            detail = withheld_message(withheld)
        if not self.library.root_set:
            status, detail = "No folder chosen: set it in Settings", ""
        elif not self.library.root_exists:
            status, detail = "Folder not found: set it in Settings", ""
        self.sidebar.resources.set_resources(resources, status, detail)
        self.library_page.refresh_status()

    def set_resources_root(self, root: str) -> None:
        self.library.set_root(Path(root))
        self.refresh_resources()
        self.library_page.reindex(full=True)

    def set_library_exclude(self, patterns: object) -> None:
        """Settings changed the exclusion list: hide what is now excluded at
        once and re-index so the database follows."""
        self.library.set_exclude([str(p) for p in patterns] if isinstance(patterns, list) else [])
        self.refresh_resources()
        self.library_page.reindex()

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
