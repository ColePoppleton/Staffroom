"""The launcher window: sidebar on the left, a stack of destinations on the
right (the Library, each tool's panel, Settings), a log drawer along the bottom.

The Library hands files to tools: its use bar (built here from each visible
tool's main file input, see :func:`staffroom.core.panel.main_file_input`)
opens a tool with the file already picked, and *Open for class* runs the
Classroom tool's own ``run`` on it, so a lesson copy made from the Library is
made exactly as one made in Classroom (the original is never touched).

Navigation has one owner: every way of reaching a page (a sidebar click, a
shortcut, ``--tool``, ``--settings``, the first-run card) ends in
:meth:`MainWindow._show`, which switches the stack and then tells the sidebar
what is showing, so the highlight cannot disagree with the page."""

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
from staffroom.core.library.model import IndexStats
from staffroom.core.library.service import ExtFilter, LibraryService
from staffroom.core.log import get_logger
from staffroom.core.panel import TextField, main_file_input
from staffroom.core.plugin import ToolPlugin, plugin_glyph
from staffroom.shell.library.page import LibraryPage, counts_detail
from staffroom.shell.library.picker import pick_resource
from staffroom.shell.library.use_bar import UseTool
from staffroom.shell.log_drawer import LogDrawer
from staffroom.shell.settings_page import SettingsPage
from staffroom.shell.sidebar import LIBRARY, SETTINGS, Sidebar
from staffroom.shell.theme import load_fonts, stylesheet
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets import FirstRunCard, make_label

log = get_logger(__name__)
CLASSROOM = "classroom"  # the tool behind the Library's Open for class


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
        load_fonts()  # the brand type, before any widget measures text
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
        self.resources = self.library_page.column  # search, filters, tree
        self.use_bar = self.library_page.preview.use_bar
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
        self.sidebar.library_requested.connect(self.show_library)
        self.sidebar.settings_requested.connect(self.show_settings)
        self.sidebar.search_requested.connect(self._on_sidebar_search)
        self.sidebar.log_toggled.connect(self.log_drawer.setVisible)
        self.settings.theme_changed.connect(self.apply_theme)
        self.settings.resources_root_changed.connect(self.set_resources_root)
        self.settings.library_exclude_changed.connect(self.set_library_exclude)
        self.settings.update_available.connect(self.sidebar.set_update_available)
        res = self.resources
        res.search_changed.connect(self._on_search)
        res.kind_changed.connect(self.library_page.set_kind)
        res.tags_changed.connect(self._on_tags_changed)
        res.show_hidden_toggled.connect(self._on_show_hidden)
        res.resource_selected.connect(self._on_resource_selected)
        res.reindex_requested.connect(self.library_page.reindex)
        res.hidden.setChecked(config.general.show_hidden)
        self.library_page.indexed.connect(self._on_indexed)
        self.library_page.resource_shown.connect(res.select)
        self.library_page.preview.tags_saved.connect(self._on_tags_saved)
        self._build_use_bar()
        self.use_bar.open_for_class.connect(self._open_shown_for_class)
        self.use_bar.tool_requested.connect(self._hand_shown_to)
        self.use_bar.classroom_requested.connect(lambda: self.go_to_tool(CLASSROOM))
        self.refresh_resources()
        QShortcut(QKeySequence("Ctrl+L"), self, self.sidebar.log_button.toggle)
        QShortcut(QKeySequence("Ctrl+Shift+L"), self, self.toggle_theme)
        QShortcut(QKeySequence("Ctrl+,"), self, self.show_settings)
        QShortcut(QKeySequence("Ctrl+K"), self, self.focus_library_search)
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_for_class)
        # ⌘1-⌘9 are the tools as the sidebar lists them, group by group (the
        # Library is ⌘K), so they skip hidden tools and follow any regrouping.
        for n, name in enumerate(self.sidebar.tool_names()[:9], 1):
            QShortcut(QKeySequence(f"Ctrl+{n}"), self, lambda name=name: self.go_to_tool(name))

        self.apply_theme(config.general.theme)
        names = self.sidebar.tool_names()
        initial = config.general.last_tool if config.general.last_tool in names else ""
        if not initial and names:
            initial = names[0]  # a fresh config opens on the first tool listed
        if self.first_run is not None:
            # The card comes first; Choose… or Not now then lands on ``initial``.
            self._first_run_target = initial
            self._show(self.first_run, "")
        elif config.general.sidebar_mode == "resources":
            self.show_library()  # the Library was the last place visited
        elif initial:
            self.show_tool(initial)
        else:
            self._show(self.welcome, "")
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
    def _show(self, page: QWidget, key: str) -> None:
        """The one place a page is shown: the stack switches and the sidebar
        highlights ``key`` (a tool name, LIBRARY, SETTINGS or "" for none)."""
        self.stack.setCurrentWidget(page)
        self.sidebar.set_current(key)

    def _remember_place(self, mode: str) -> None:
        """ "tools" or "resources": where the next launch opens (config's
        ``sidebar_mode``; the Library is "resources", a tool "tools")."""
        if self.config.general.sidebar_mode != mode:
            self.config.general.sidebar_mode = mode
            self._save_config()

    def panel_for(self, name: str) -> ToolPanel:
        if name not in self.panels:
            plugin = next(p for p in self.plugins if p.name == name)
            panel = ToolPanel(plugin, self.config, resources=self.library)
            self.panels[name] = panel
            self.stack.addWidget(panel)
        return self.panels[name]

    def show_tool(self, name: str) -> None:
        panel = self.panel_for(name)
        self._show(panel, name)  # a hidden tool is in no row: nothing lit
        self._remember_place("tools")
        if self.config.general.last_tool != name:
            self.config.general.last_tool = name
            self._save_config()
        log.debug("showing %s", name)

    def show_library(self) -> None:
        self._show(self.library_page, LIBRARY)
        self._remember_place("resources")

    def _save_config(self) -> None:
        """Remember a choice (last tool, sidebar mode, theme…) in config.toml.
        A config home that cannot be written (#65, #74) keeps the choice for
        this session: ``Config.save`` logs it once and the Settings page says
        so, instead of a traceback per click."""
        self.settings.show_save_result(self.config.save())

    def show_settings(self) -> None:
        self._show(self.settings, SETTINGS)

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
            self._show(self.welcome, "")

    # -- shortcuts -------------------------------------------------------
    def focus_library_search(self) -> None:
        """⌘K: the Library, with its search box focused and selected."""
        self.show_library()
        self.resources.search.setFocus()
        self.resources.search.selectAll()

    def _on_sidebar_search(self, text: str) -> None:
        """Typing in the sidebar's search field carries on in the Library's:
        the text moves across and the cursor follows it."""
        self.show_library()
        self.resources.search.setText(text)
        self.resources.search.setFocus()
        self.resources.search.end(False)
        self.sidebar.search.clear()

    def go_to_tool(self, name: str, path: Path | None = None) -> None:
        """Show ``name``, listed or hidden (``staffroom --tool hello``), with
        ``path`` already picked in its main file input when given. Unknown
        names do nothing."""
        if not any(p.name == name for p in self.plugins):
            return
        self.show_tool(name)
        if path is not None:
            panel = self.panel_for(name)
            file_input = main_file_input(panel.spec)
            if file_input is not None:
                panel.set_input_path(file_input.key, path)

    def open_for_class(self) -> None:
        """⌘O. On the Library with a file showing: open it for class (or, with
        no lesson label yet, put the cursor in the label field; Enter then
        opens it). Anywhere else: Classroom with the library picker open."""
        if not any(p.name == CLASSROOM for p in self.plugins):
            return
        bar = self.use_bar
        showing = self.stack.currentWidget() is self.library_page
        if showing and bar.resource is not None and bar.class_group.isVisibleTo(bar):
            if bar.label.text().strip():
                bar.submit()
            else:
                bar.focus_label()
            return
        self.go_to_tool(CLASSROOM)
        panel = self.panel_for(CLASSROOM)
        file_input = main_file_input(panel.spec)
        picker = panel.resource_pickers.get(file_input.key) if file_input else None
        if picker is not None:
            picker.pick_from_library()

    # -- the library's use bar -------------------------------------------
    def _build_use_bar(self) -> None:
        """One button per visible tool that takes a file, in sidebar order,
        from the tool's own panel spec; Classroom is *Open for class*."""
        by_name = {p.name: p for p in self.visible_plugins}
        tools: list[UseTool] = []
        for name in self.sidebar.tool_names():
            plugin = by_name.get(name)
            if plugin is None or name == CLASSROOM:
                continue
            spec = plugin.panel_spec()
            file_input = main_file_input(spec)
            if file_input is not None:
                tools.append(UseTool(name, spec.title or name, plugin_glyph(plugin), file_input))
        classroom = next((p for p in self.plugins if p.name == CLASSROOM), None)
        label = None
        if classroom is not None:
            label = next(
                (w for w in classroom.panel_spec().inputs if isinstance(w, TextField)), None
            )
        self.use_bar.set_tools(tools, classroom=classroom is not None, label=label)

    def shown_path(self) -> Path | None:
        """The file the Library's preview shows, as an absolute path."""
        resource = self.library_page.preview.resource
        return self.library.absolute(resource.rel_path) if resource else None

    def _hand_shown_to(self, name: str) -> None:
        path = self.shown_path()
        if path is not None:
            self.go_to_tool(name, path)

    def _open_shown_for_class(self, label: str) -> None:
        path = self.shown_path()
        if path is not None:
            self.open_in_classroom(path, label)

    def open_in_classroom(self, path: Path, label: str) -> None:
        """Open ``path`` for class under ``label`` through the Classroom
        tool's own run (copy into the sessions folder, launch the editor on
        the copy). The Library stays in view; its use bar says how it went."""
        panel = self.panel_for(CLASSROOM)
        file_input = main_file_input(panel.spec)
        label_key = next((w.key for w in panel.spec.inputs if isinstance(w, TextField)), None)
        if file_input is None or label_key is None:
            self.use_bar.show_status("Classroom cannot take a file here.", ok=False)
            return
        if panel.worker is not None and panel.worker.isRunning():
            self.use_bar.show_status("Classroom is still making the last copy.", ok=False)
            return
        panel.set_input_path(file_input.key, path)
        panel.set_text(label_key, label)
        before = panel.worker
        panel.run_finished.connect(self._on_class_copy, Qt.ConnectionType.SingleShotConnection)
        panel.start_run()
        if panel.worker is before:  # refused before starting (a missing input)
            panel.run_finished.disconnect(self._on_class_copy)
            self.use_bar.show_status(panel.strip.text(), ok=False)

    def _on_class_copy(self, ok: bool) -> None:
        panel = self.panels[CLASSROOM]
        result = panel.last_result
        if ok and result is not None and result.files:
            copy = result.files[0]
            where = f"{copy.parent.parent.name}/{copy.parent.name}"
            text = f"{result.summary or 'Opened for class'}  ·  {where}"
            self.use_bar.show_status(text, ok=True, link=True)
        else:
            self.use_bar.show_status(panel.strip.text() or "Could not open it for class", ok=False)

    # -- resources -------------------------------------------------------
    def _on_search(self, text: str) -> None:
        self.library_page.set_query(text)
        if text:
            self.show_library()

    def _on_show_hidden(self, show: bool) -> None:
        self.config.general.show_hidden = show
        self._save_config()
        self.library_page.set_show_hidden(show)
        self.refresh_resources()

    def _on_tags_changed(self, _tags: object) -> None:
        """The tag filter changed (#111): narrow the tree and the results."""
        self.refresh_resources()
        self.library_page.refresh_search()

    def _on_tags_saved(self, _rel_path: str) -> None:
        """A file's tags changed: the filter's counts follow at once, and
        while it is on, so do the tree and the results."""
        if self.resources.chosen_tags():
            self._on_tags_changed(None)
        else:
            show_hidden = self.config.general.show_hidden
            self.resources.set_tag_counts(self.library.tag_counts(include_hidden=show_hidden))

    def _on_resource_selected(self, rel_path: str) -> None:
        self.show_library()
        self.library_page.show_resource(rel_path)

    def _on_indexed(self, stats: IndexStats) -> None:
        self.refresh_resources()
        self.resources.set_indexing(False)
        if self.first_run is not None and self._first_run_pending:
            self.first_run.finish_indexing(stats.summary())
            self.finish_first_run()

    def refresh_resources(self) -> None:
        show_hidden = self.config.general.show_hidden
        resources = self.library.resources(include_hidden=show_hidden)
        # One tally for the footer and the Resources header (#30): the
        # sidebar's number is the length of the list it shows.
        counts = self.library.counts()
        status = counts.status_line(show_hidden=show_hidden, sep="\n")
        detail = counts_detail(counts) if counts.indexed else ""
        if self.library.unavailable_reason is not None:
            # A read-only config home (#65): say so instead of a count that
            # can never change, and offer nothing that would try to write.
            status, detail = self.library.unavailable_reason, self.library.unavailable_detail()
        elif not self.library.root_set:
            status, detail = "No folder chosen: set it in Settings", ""
        elif not self.library.root_exists:
            status, detail = "Folder not found: set it in Settings", ""
        # The tag filter (#111): its counts are over the files listed, and it
        # narrows the tree only; the counts above stay the library's own.
        self.resources.set_tag_counts(self.library.tag_counts(include_hidden=show_hidden))
        chosen = self.resources.chosen_tags()
        shown = resources
        if chosen:
            shown = self.library.resources(include_hidden=show_hidden, tags=chosen)
            n = len(shown)
            status = f"{n} file{'s' if n != 1 else ''} tagged {' + '.join(chosen)}\n{status}"
        self.resources.set_resources(shown, status, detail, filtered=bool(chosen))
        self.resources.set_library_state(
            can_index=self.library.available, can_search=self.library.searchable
        )
        # The count beside Library is the same tally as the column's footer.
        self.sidebar.set_library_count(str(len(resources)) if counts.indexed else "")
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

    def _pick_resource(self, filter_ext: ExtFilter) -> Path | None:
        return pick_resource(self.library, filter_ext, self)

    # -- theming ---------------------------------------------------------
    def apply_theme(self, theme: str) -> None:
        app = QApplication.instance()
        if app is not None and isinstance(app, QApplication):
            app.setStyleSheet(stylesheet(_as_theme(theme)))
        self.sidebar.set_theme(_as_theme(theme))
        self.library_page.set_theme(theme)
        if self.settings.theme.currentText() != theme:
            self.settings.theme.blockSignals(True)
            self.settings.theme.setCurrentText(theme)
            self.settings.theme.blockSignals(False)
        if self.config.general.theme != theme:
            self.config.general.theme = _as_theme(theme)
            self._save_config()

    def toggle_theme(self) -> None:
        self.apply_theme("light" if self.config.general.theme == "dark" else "dark")


def _as_theme(value: str) -> Theme:
    return "light" if value == "light" else "dark"
