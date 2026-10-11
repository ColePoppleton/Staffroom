"""Renders one tool's PanelSpec as a workbench and drives its runs.

Below a one-line header (title and description), two panes side by side:

* the **inputs pane** on the left, a fixed width (390 px, narrowing to 340 px
  at the window's minimum width) with its own scroll. Each input widget is a
  hairline-separated :class:`InputGroup`, and the run button sits at the
  pane's foot (:class:`RunBar`, ⌘↵ from anywhere in the window) with where the
  next run will write. A group whose ``PanelSpec.shown_when`` does not hold is
  hidden with its hairline, and the tool gets its empty value.
* the **output pane** filling the rest (:class:`OutputPane`): the result strip
  on top (how the run went, the files it wrote as buttons), the main output(s)
  as tabs, secondary outputs under them, the run log behind *Details*.

Results never push the inputs away and nothing scrolls on its own: changing
one option and running again is one click (or ⌘↵) with both sides in view.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QResizeEvent, QShortcut, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from staffroom.core.config import Config
from staffroom.core.csvio import read_table
from staffroom.core.library.service import ResourceService
from staffroom.core.log import get_logger
from staffroom.core.panel import (
    DEFAULT_OPEN_LABEL,
    CardList,
    Choice,
    CodeSource,
    CodeValue,
    EditableTable,
    FilePicker,
    FolderPicker,
    OptionsForm,
    PanelSpec,
    ResourcePicker,
    ResultsTable,
    TablePreview,
    TextArea,
    TextField,
)
from staffroom.core.plugin import RunContext, RunResult, SupportsActions, ToolError, ToolPlugin
from staffroom.shell.widgets import (
    CardListWidget,
    ChoiceWidget,
    CodeSourceWidget,
    CompactTableWidget,
    Divider,
    EditableTableWidget,
    InputGroup,
    LineLink,
    LoadSummaryWidget,
    OptionsFormWidget,
    OutputPane,
    PathPickerWidget,
    ResourcePickerWidget,
    RunBar,
    TablePreviewWidget,
    TableWidget,
    TextAreaWidget,
    TextFieldWidget,
    make_label,
)
from staffroom.shell.widgets.elided_label import ElidedLabel
from staffroom.shell.widgets.run_bar import RUN_SHORTCUT_TEXT, RUN_SHORTCUTS
from staffroom.shell.worker import RunWorker

log = get_logger(__name__)

INPUTS_WIDTH = 390
INPUTS_MIN_WIDTH = 340  # at the window's minimum width (1040 px)
OUTPUT_MIN_WIDTH = 440


class ToolPanel(QWidget):
    run_started = Signal()
    run_finished = Signal(bool)  # ok

    def __init__(
        self,
        plugin: ToolPlugin,
        config: Config,
        parent: QWidget | None = None,
        *,
        resources: ResourceService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ToolPanel")
        self.plugin = plugin
        self.config = config
        self.resources = resources
        self.spec: PanelSpec = plugin.panel_spec()
        self.pickers: dict[str, PathPickerWidget] = {}
        self.resource_pickers: dict[str, ResourcePickerWidget] = {}
        self.text_fields: dict[str, TextFieldWidget] = {}
        self.text_areas: dict[str, TextAreaWidget] = {}
        self.code_sources: dict[str, CodeSourceWidget] = {}
        self.line_links: dict[str, LineLink] = {}
        self._refreshed = False
        self._quiet = False
        self.forms: dict[str, OptionsFormWidget] = {}
        self.grids: dict[str, EditableTableWidget | CompactTableWidget] = {}
        self.choices: dict[str, ChoiceWidget] = {}
        self.previews: dict[str, TablePreviewWidget] = {}
        self.summaries: dict[str, LoadSummaryWidget] = {}
        self.groups: dict[str, InputGroup] = {}
        self.dividers: dict[str, Divider] = {}  # the hairline over each group but the first
        self.worker: RunWorker | None = None
        self.last_result: RunResult | None = None
        self._last_ok = False
        self._is_run = False  # the worker running is a run (not a row action)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        panes = QHBoxLayout()
        panes.setContentsMargins(0, 0, 0, 0)
        panes.setSpacing(0)
        root.addLayout(panes, 1)

        # -- inputs pane: groups in a scroll, the run bar pinned at the foot
        self.inputs_pane = QWidget()
        self.inputs_pane.setObjectName("InputsPane")
        self.inputs_pane.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.inputs_pane.setFixedWidth(INPUTS_WIDTH)
        inputs_layout = QVBoxLayout(self.inputs_pane)
        inputs_layout.setContentsMargins(0, 0, 0, 0)
        inputs_layout.setSpacing(0)
        self.inputs_scroll = QScrollArea()
        self.inputs_scroll.setObjectName("InputsScroll")
        self.inputs_scroll.setWidgetResizable(True)
        self.inputs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inputs_body = QWidget()
        inputs_body.setObjectName("InputsBody")
        self.inputs_layout = QVBoxLayout(inputs_body)
        self.inputs_layout.setContentsMargins(22, 4, 22, 12)
        self.inputs_layout.setSpacing(0)
        self.inputs_scroll.setWidget(inputs_body)
        inputs_layout.addWidget(self.inputs_scroll, 1)
        self._build_inputs()
        self.inputs_layout.addStretch(1)
        if self.spec.shown_when:
            for form in self.forms.values():
                form.changed.connect(self._sync_shown)
            for choice in self.choices.values():
                choice.changed.connect(self._sync_shown)
            self._sync_shown()

        writes_to = self.spec.writes_to
        self.run_bar = (
            RunBar(self.spec.run_label, verb=writes_to.verb)
            if writes_to
            else RunBar(self.spec.run_label)
        )
        self.run_bar.run_requested.connect(self.start_run)
        inputs_layout.addWidget(self.run_bar)
        panes.addWidget(self.inputs_pane)

        # -- output pane
        self.results = OutputPane(
            self.spec.outputs,
            empty_text=f"Press {self.spec.run_label} ({RUN_SHORTCUT_TEXT}) "
            "and the result appears here.",
            main_layout=self.spec.main_layout,
            open_label=writes_to.open_label if writes_to else DEFAULT_OPEN_LABEL,
            details_key=plugin.name,
        )
        self.results.action_requested.connect(self.start_action)
        self.results.open_requested.connect(self.open_file)
        self.strip = self.results.strip
        self.strip.open_requested.connect(self.open_file)
        self.strip.reveal_requested.connect(self.reveal_file)
        self.strip.folder_requested.connect(self.open_folder)
        panes.addWidget(self.results, 1)
        self._link_lines()

        # ⌘↵ runs the tool on show; a hidden panel's shortcut stays inactive.
        self.run_shortcuts = [
            QShortcut(QKeySequence(keys), self, self.run_bar.button.click) for keys in RUN_SHORTCUTS
        ]

        for picker in self.pickers.values():
            picker.changed.connect(self._show_output_folder)
        for rpicker in self.resource_pickers.values():
            rpicker.changed.connect(self._show_output_folder)
        for code in self.code_sources.values():
            code.changed.connect(self._show_output_folder)
            code.changed.connect(self._suggest)
        for path_picker in self.pickers.values():
            path_picker.changed.connect(self._suggest)
        for rpicker in self.resource_pickers.values():
            rpicker.changed.connect(self._suggest)
        if writes_to:  # a tool's own destination may follow a typed input, e.g. a label
            for text_field in self.text_fields.values():
                text_field.edit.textChanged.connect(self._show_output_folder)
        self._show_output_folder()

    # -- building --------------------------------------------------------
    def _build_header(self) -> QWidget:
        header = QWidget()
        header.setObjectName("PanelHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(28, 16, 28, 12)
        layout.setSpacing(14)
        title = make_label(self.spec.title, "title")
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignBaseline)
        # One line that never widens the window: elided, whole in the tooltip.
        description = ElidedLabel(self.spec.description)
        description.setProperty("role", "subtitle")
        description.setVisible(bool(self.spec.description))
        layout.addWidget(description, 1, Qt.AlignmentFlag.AlignBaseline)
        return header

    def _build_inputs(self) -> None:
        for spec in self.spec.inputs:
            if isinstance(spec, FilePicker | FolderPicker):
                group = InputGroup(spec.label, spec.help)
                picker = PathPickerWidget(spec)
                group.add(picker)
                self.pickers[spec.key] = picker
            elif isinstance(spec, ResourcePicker):
                group = InputGroup(spec.label, spec.help)
                rpicker = ResourcePickerWidget(spec, self.resources)
                group.add(rpicker)
                self.resource_pickers[spec.key] = rpicker
            elif isinstance(spec, CodeSource):
                group = InputGroup(spec.label, spec.help)
                code = CodeSourceWidget(spec, self.resources)
                group.add(code)
                group.add_trailing(code.mode_link)
                self.code_sources[spec.key] = code
                if spec.choice is not None and code.choice is not None:
                    self.choices[spec.choice.key] = code.choice
            elif isinstance(spec, TextField):
                group = InputGroup(spec.label, spec.help)
                field = TextFieldWidget(spec)
                group.add(field)
                self.text_fields[spec.key] = field
            elif isinstance(spec, TextArea):
                group = InputGroup(spec.label, spec.help)
                area = TextAreaWidget(spec)
                group.add(area)
                self.text_areas[spec.key] = area
            elif isinstance(spec, TablePreview) and spec.compact:
                # The summary sits under its file picker, in the same group.
                summary = LoadSummaryWidget(spec)
                source_group = self.groups[spec.source]
                source_group.body.addWidget(summary)
                source_group.add_trailing(summary.preview_button)
                self.summaries[spec.key] = summary
                self.pickers[spec.source].changed.connect(
                    lambda path, s=spec, w=summary: self._load_preview(s, w, path)
                )
                self.groups[spec.key] = source_group
                continue
            elif isinstance(spec, TablePreview):
                group = InputGroup(spec.label)
                preview = TablePreviewWidget(spec)
                group.add(preview)
                self.previews[spec.key] = preview
                self.pickers[spec.source].changed.connect(
                    lambda path, s=spec, w=preview: self._load_preview(s, w, path)
                )
            elif isinstance(spec, Choice):
                group = InputGroup(spec.label, spec.help)
                choice = ChoiceWidget(spec)
                group.add(choice)
                self.choices[spec.key] = choice
            elif isinstance(spec, OptionsForm):
                group = InputGroup(spec.label)
                form = OptionsFormWidget.for_spec(spec)
                group.add(form)
                self.forms[spec.key] = form
            elif isinstance(spec, EditableTable):
                group = InputGroup(spec.label, spec.help)
                grid: EditableTableWidget | CompactTableWidget
                if spec.compact:
                    grid = CompactTableWidget(spec)
                    group.add_trailing(grid.save_button)
                else:
                    grid = EditableTableWidget(spec)
                group.add(grid)
                self.grids[spec.key] = grid
                if spec.choice is not None and grid.choice is not None:
                    self.choices[spec.choice.key] = grid.choice
                if spec.preset_action:
                    grid.preset_saved.connect(
                        lambda name, table, action=spec.preset_action: self._save_preset(
                            action, name, table
                        )
                    )
            else:  # pragma: no cover - exhaustive over InputWidget
                msg = f"unknown input widget {spec!r}"
                raise TypeError(msg)
            if self.groups:
                self.dividers[spec.key] = Divider()
                self.inputs_layout.addWidget(self.dividers[spec.key])
            self.groups[spec.key] = group
            self.inputs_layout.addWidget(group)

    def hidden_inputs(self) -> frozenset[str]:
        """The inputs whose ``PanelSpec.shown_when`` does not hold just now."""
        return self.spec.hidden_inputs(self.collect_inputs())

    def _sync_shown(self, *_: object) -> None:
        """Show the groups that apply and hide the rest, each with the hairline
        over it; the first group shown never has one."""
        hidden = self.hidden_inputs()
        first = True
        seen: set[int] = set()
        for key, group in self.groups.items():
            if id(group) in seen:  # a compact preview shares its picker's group
                continue
            seen.add(id(group))
            shown = key not in hidden
            group.setVisible(shown)
            divider = self.dividers.get(key)
            if divider is not None:
                divider.setVisible(shown and not first)
            first = first and not shown

    def _link_lines(self) -> None:
        """Results tables and card lists whose rows name lines of the program
        (trace steps, bug variants) light those lines in its code view, and back."""
        for spec in self.spec.outputs:
            if not (isinstance(spec, ResultsTable | CardList) and spec.line_column):
                continue
            code = self.code_sources.get(spec.line_source)
            if code is None:
                continue
            rows: TableWidget | CardListWidget
            if spec.key in self.results.tables:
                rows = self.results.tables[spec.key][1]
            elif spec.key in self.results.card_lists:
                rows = self.results.card_lists[spec.key]
            else:
                continue
            self.line_links[spec.key] = LineLink(rows, spec.line_column, code.view)

    def _suggest(self, *_: object) -> None:
        """Let the tool set choices from what was picked or pasted (#62)."""
        if self.spec.suggest is None:
            return
        try:
            values = dict(self.spec.suggest(self.collect_inputs()))
        except Exception as exc:  # a pure hint: never break the panel over it
            log.warning("%s suggest failed: %s", self.plugin.name, exc)
            return
        for key, value in values.items():
            choice = self.choices.get(key)
            if choice is not None:
                choice.set_value(value)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """The inputs pane keeps 390 px while the output pane has room, and
        gives up to 50 px of it at the window's minimum width."""
        super().resizeEvent(event)
        width = max(INPUTS_MIN_WIDTH, min(INPUTS_WIDTH, event.size().width() - OUTPUT_MIN_WIDTH))
        if width != self.inputs_pane.width():
            self.inputs_pane.setFixedWidth(width)

    def _load_preview(
        self,
        spec: TablePreview,
        preview: TablePreviewWidget | LoadSummaryWidget,
        path: Path | None,
    ) -> None:
        if path is None:
            preview.set_table(None)
            return
        try:
            table = read_table(path, flag=spec.flag)
            preview.set_table(table)
            if table.dropped_columns:
                self.results.append_log(
                    f"Dropped identifier column(s) from {path.name}: "
                    + ", ".join(table.dropped_columns)
                )
        except ToolError as exc:  # already a one-line message naming the file
            log.warning("could not preview %s: %s", path, exc)
            preview.set_error(str(exc))
        except Exception as exc:
            log.warning("could not preview %s: %s", path, exc)
            preview.set_error(f"Could not read {path.name}: {exc}")

    # -- values ----------------------------------------------------------
    def collect_inputs(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key, picker in self.pickers.items():
            values[key] = picker.value()
        for key, rpicker in self.resource_pickers.items():
            values[key] = rpicker.value()
        for key, field in self.text_fields.items():
            values[key] = field.value()
        for key, area in self.text_areas.items():
            values[key] = area.value()
        for key, code in self.code_sources.items():
            values[key] = code.value()
        for key, form in self.forms.items():
            values[key] = form.value()
        for key, grid in self.grids.items():
            values[key] = grid.value()
        for key, choice in self.choices.items():
            values[key] = choice.value()
        # An input that does not apply hands over its empty value (#123).
        return self.spec.passed(values)

    def set_input_path(self, key: str, path: Path | None) -> None:
        if key in self.code_sources:
            self.code_sources[key].set_path(path)
        elif key in self.resource_pickers:
            self.resource_pickers[key].set_path(path)
        else:
            self.pickers[key].set_path(path)

    def set_text(self, key: str, text: str) -> None:
        """Type into a text input; for a code source, paste ``text`` instead
        of a file."""
        if key in self.code_sources:
            self.code_sources[key].set_pasted(text)
        elif key in self.text_areas:
            self.text_areas[key].set_value(text)
        else:
            self.text_fields[key].set_value(text)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        if not self._refreshed:
            self._refreshed = True
            self.refresh_tables()

    def first_file_key(self) -> str | None:
        for spec in self.spec.inputs:
            if isinstance(spec, FilePicker | ResourcePicker | CodeSource):
                return spec.key
        return None

    def missing_inputs(self, inputs: dict[str, Any]) -> list[str]:
        missing: list[str] = []
        hidden = self.spec.hidden_inputs(inputs)  # what is not shown is not asked for
        for s in self.spec.inputs:
            if s.key in hidden:
                continue
            if isinstance(s, FilePicker | FolderPicker | ResourcePicker) and s.required:
                if inputs.get(s.key) is None:
                    missing.append(s.label)
            elif isinstance(s, TextField | TextArea) and s.required and not inputs.get(s.key):
                missing.append(s.label)
            elif isinstance(s, CodeSource) and s.required:
                code = inputs.get(s.key)
                if not isinstance(code, CodeValue) or (code.path is None and not code.text.strip()):
                    missing.append(s.label)
        return missing

    def output_dir(self, inputs: dict[str, Any]) -> Path:
        first = self.first_file_key()
        anchor = inputs.get(first) if first else None
        if isinstance(anchor, CodeValue):
            anchor = anchor.path
        return self.config.output_dir_for(anchor, self.plugin.name)

    def destination(self, inputs: dict[str, Any]) -> Path:
        """Where the next run's files land: the tool's own ``writes_to`` folder
        if its panel names one, else the shared output folder."""
        if self.spec.writes_to:
            return self.spec.writes_to.folder(inputs, self.config)
        return self.output_dir(inputs)

    def _show_output_folder(self, *_: object) -> None:
        """Say where the next run will write, before it starts: under the run
        button, and as the strip's folder chip until the first run."""
        folder = self.destination(self.collect_inputs())
        self.run_bar.set_output_folder(folder)
        self.strip.set_destination(folder)

    # -- the strip's chips -------------------------------------------------
    def open_file(self, path: Path) -> None:
        """Hand a written file to its own app (Office files are never parsed)."""
        if self.resources is not None:
            self.resources.open_externally(path)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def reveal_file(self, path: Path) -> None:
        reveal = getattr(self.resources, "reveal", None)
        if callable(reveal):
            reveal(path)
        else:
            self.open_folder(path.parent)

    def open_folder(self, folder: Path) -> None:
        # The default folder may not exist until the first write; make it so
        # the chip works before the first run too.
        folder.mkdir(parents=True, exist_ok=True)
        self.open_file(folder)

    # -- running ---------------------------------------------------------
    def start_run(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        for code in self.code_sources.values():
            code.reload()  # show what the run will read, if the file was saved since
        inputs = self.collect_inputs()
        missing = self.missing_inputs(inputs)
        if missing:
            self.strip.show_failure(f"Fill in: {', '.join(missing)}")
            return
        self.results.clear()
        log.info("running %s", self.plugin.name)
        worker = RunWorker(
            self.plugin, inputs, self.config, self.output_dir(inputs), resources=self.resources
        )
        self._launch(worker, run=True)

    def start_action(self, name: str, row: dict[str, Any]) -> None:
        """A row action from an ActionTable, run off the GUI thread."""
        if not isinstance(self.plugin, SupportsActions):
            self.strip.show_failure(f"{self.plugin.name} has no actions")
            return
        if self.worker is not None and self.worker.isRunning():
            return
        plugin = self.plugin
        inputs = self.collect_inputs()
        log.info("%s action %s", plugin.name, name)
        worker = RunWorker(
            self.plugin,
            inputs,
            self.config,
            self.output_dir(inputs),
            resources=self.resources,
            job=lambda ctx: plugin.act(name, row, ctx),
        )
        self._launch(worker, quiet=name in self.spec.refresh_actions())

    def _save_preset(self, action: str, name: str, table: Any) -> None:
        """Persist a preset through the plugin, synchronously (it is a config write)."""
        if not isinstance(self.plugin, SupportsActions):
            return
        ctx = RunContext(
            config=self.config,
            output_dir=self.output_dir(self.collect_inputs()),
            resources=self.resources,
        )
        try:
            result = self.plugin.act(action, {"name": name, "table": table}, ctx)
        except ToolError as exc:  # already a message for the teacher (#74)
            self.strip.show_failure(str(exc))
            self.results.append_log(str(exc))
            return
        except Exception as exc:
            self.strip.show_failure(f"Could not save preset: {exc}")
            return
        if not (result.outcome or result.summary):
            result.summary = f"Saved preset {name}"
        self.strip.show_result(result)
        self.results.append_log(result.summary or result.outcome)

    def refresh_tables(self) -> None:
        """Run the refresh actions synchronously; they are cheap listings."""
        if not isinstance(self.plugin, SupportsActions):
            return
        plugin = self.plugin
        ctx = RunContext(
            config=self.config,
            output_dir=self.output_dir(self.collect_inputs()),
            resources=self.resources,
        )
        for name in self.spec.refresh_actions():
            try:
                self.results.apply(plugin.act(name, {}, ctx), run=False)
            except Exception as exc:
                log.warning("%s refresh %s failed: %s", plugin.name, name, exc)
                self.results.append_log(f"Could not refresh: {exc}")

    def _launch(self, worker: RunWorker, *, quiet: bool = False, run: bool = False) -> None:
        self._quiet = quiet
        self._is_run = run
        self.run_bar.set_running(True)
        if not quiet:
            self.strip.set_running()
        self.run_started.emit()
        worker.progress.connect(self._on_progress)
        worker.log.connect(self.results.append_log)
        if not quiet:
            worker.warned.connect(self.strip.add_warning)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_failure)
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker
        worker.start()

    def _on_progress(self, fraction: float, message: str) -> None:
        self.run_bar.set_progress(fraction)
        if not self._quiet:
            self.strip.set_progress(message)

    def _on_worker_finished(self) -> None:
        """Runs on the GUI thread once the worker's run() has returned. Waiting
        here guarantees the QThread is fully stopped before anyone (tests,
        window teardown) can destroy it."""
        if self.worker is not None:
            self.worker.wait()
        self.run_bar.set_running(False)
        if self._last_ok and not self._quiet:
            self._refresh_after_change()
        self.run_finished.emit(self._last_ok)

    def _refresh_after_change(self) -> None:
        """After a run or action, re-list ActionTables unless the result
        already carried them."""
        result = self.last_result
        keys_present = set(result.tables) if result else set()
        if all(k in keys_present for k in self.results.action_tables):
            return
        self.refresh_tables()

    def _on_success(self, result: RunResult) -> None:
        self.last_result = result
        self.results.apply(result, run=self._is_run)
        self.run_bar.set_progress(1.0)
        if not self._quiet:
            self.strip.show_result(result)
        log.info("%s finished: %s", self.plugin.name, result.summary)
        self._last_ok = True

    def _on_failure(self, message: str, is_bug: bool) -> None:
        self.last_result = None
        headline = message.strip().splitlines()[-1] if is_bug else message
        self.strip.show_failure(headline)
        self.results.append_log(message)
        (log.error if is_bug else log.warning)("%s failed: %s", self.plugin.name, headline)
        self._last_ok = False
