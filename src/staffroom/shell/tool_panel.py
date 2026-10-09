"""Renders one tool's PanelSpec as a workbench and drives its runs.

Below a one-line header (title and description), two panes side by side:

* the **inputs pane** on the left, a fixed width (390 px, narrowing to 340 px
  at the window's minimum width) with its own scroll. Each input widget is a
  hairline-separated :class:`InputGroup`, and the run button sits at the
  pane's foot (:class:`RunBar`, ⌘↵ from anywhere in the window) with where the
  run will write.
* the **output pane** filling the rest (:class:`OutputPane`): the main
  output(s) as tabs, secondary outputs under them, the log at the foot.

Results never push the inputs away and nothing scrolls on its own: changing
one option and running again is one click (or ⌘↵) with both sides in view.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QResizeEvent, QShortcut, QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from staffroom.core.config import Config
from staffroom.core.csvio import read_table
from staffroom.core.library.service import ResourceService
from staffroom.core.log import get_logger
from staffroom.core.panel import (
    EditableTable,
    FilePicker,
    FolderPicker,
    OptionsForm,
    PanelSpec,
    ResourcePicker,
    TablePreview,
    TextArea,
    TextField,
)
from staffroom.core.plugin import RunContext, RunResult, SupportsActions, ToolError, ToolPlugin
from staffroom.shell.widgets import (
    Divider,
    EditableTableWidget,
    InputGroup,
    OptionsFormWidget,
    OutputPane,
    PathPickerWidget,
    ResourcePickerWidget,
    RunBar,
    TablePreviewWidget,
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
        self._refreshed = False
        self._quiet = False
        self._action = False
        self.forms: dict[str, OptionsFormWidget] = {}
        self.grids: dict[str, EditableTableWidget] = {}
        self.previews: dict[str, TablePreviewWidget] = {}
        self.groups: dict[str, InputGroup] = {}
        self.worker: RunWorker | None = None
        self.last_result: RunResult | None = None
        self._last_ok = False

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

        writes_to = self.spec.writes_to
        self.run_bar = (
            RunBar(self.spec.run_label, verb=writes_to.verb, open_label=writes_to.open_label)
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
        )
        self.results.action_requested.connect(self.start_action)
        panes.addWidget(self.results, 1)

        # ⌘↵ runs the tool on show; a hidden panel's shortcut stays inactive.
        self.run_shortcuts = [
            QShortcut(QKeySequence(keys), self, self.run_bar.button.click) for keys in RUN_SHORTCUTS
        ]

        for picker in self.pickers.values():
            picker.changed.connect(self._show_output_folder)
        for rpicker in self.resource_pickers.values():
            rpicker.changed.connect(self._show_output_folder)
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
            elif isinstance(spec, TablePreview):
                group = InputGroup(spec.label)
                preview = TablePreviewWidget(spec)
                group.add(preview)
                self.previews[spec.key] = preview
                self.pickers[spec.source].changed.connect(
                    lambda path, p=preview: self._load_preview(p, path)
                )
            elif isinstance(spec, OptionsForm):
                group = InputGroup(spec.label)
                form = OptionsFormWidget(spec.schema, spec.presets)
                group.add(form)
                self.forms[spec.key] = form
            elif isinstance(spec, EditableTable):
                group = InputGroup(spec.label, spec.help)
                grid = EditableTableWidget(spec)
                group.add(grid)
                self.grids[spec.key] = grid
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
                self.inputs_layout.addWidget(Divider())
            self.groups[spec.key] = group
            self.inputs_layout.addWidget(group)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """The inputs pane keeps 390 px while the output pane has room, and
        gives up to 50 px of it at the window's minimum width."""
        super().resizeEvent(event)
        width = max(INPUTS_MIN_WIDTH, min(INPUTS_WIDTH, event.size().width() - OUTPUT_MIN_WIDTH))
        if width != self.inputs_pane.width():
            self.inputs_pane.setFixedWidth(width)

    def _load_preview(self, preview: TablePreviewWidget, path: Path | None) -> None:
        if path is None:
            preview.set_table(None)
            return
        try:
            table = read_table(path)
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
        for key, form in self.forms.items():
            values[key] = form.value()
        for key, grid in self.grids.items():
            values[key] = grid.value()
        return values

    def set_input_path(self, key: str, path: Path | None) -> None:
        if key in self.resource_pickers:
            self.resource_pickers[key].set_path(path)
        else:
            self.pickers[key].set_path(path)

    def set_text(self, key: str, text: str) -> None:
        if key in self.text_areas:
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
            if isinstance(spec, FilePicker | ResourcePicker):
                return spec.key
        return None

    def missing_inputs(self, inputs: dict[str, Any]) -> list[str]:
        missing: list[str] = []
        for s in self.spec.inputs:
            if isinstance(s, FilePicker | FolderPicker | ResourcePicker) and s.required:
                if inputs.get(s.key) is None:
                    missing.append(s.label)
            elif isinstance(s, TextField | TextArea) and s.required and not inputs.get(s.key):
                missing.append(s.label)
        return missing

    def output_dir(self, inputs: dict[str, Any]) -> Path:
        first = self.first_file_key()
        anchor = inputs.get(first) if first else None
        return self.config.output_dir_for(anchor, self.plugin.name)

    def destination(self, inputs: dict[str, Any]) -> Path:
        """Where the next run's files land: the tool's own ``writes_to`` folder
        if its panel names one, else the shared output folder."""
        if self.spec.writes_to:
            return self.spec.writes_to.folder(inputs, self.config)
        return self.output_dir(inputs)

    def _show_output_folder(self, *_: object) -> None:
        """Tell the run bar where the next run will write, before it starts."""
        self.run_bar.set_output_folder(self.destination(self.collect_inputs()))

    # -- running ---------------------------------------------------------
    def start_run(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        inputs = self.collect_inputs()
        missing = self.missing_inputs(inputs)
        if missing:
            self.run_bar.set_status(f"Fill in: {', '.join(missing)}", "danger")
            return
        self.results.clear()
        log.info("running %s", self.plugin.name)
        worker = RunWorker(
            self.plugin, inputs, self.config, self.output_dir(inputs), resources=self.resources
        )
        self._launch(worker)

    def start_action(self, name: str, row: dict[str, Any]) -> None:
        """A row action from an ActionTable, run off the GUI thread."""
        if not isinstance(self.plugin, SupportsActions):
            self.run_bar.set_status(f"{self.plugin.name} has no actions", "danger")
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
        self._launch(worker, quiet=name in self.spec.refresh_actions(), action=True)

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
        except Exception as exc:
            self.run_bar.set_status(f"Could not save preset: {exc}", "danger")
            return
        self.run_bar.set_status(result.summary or f"Saved preset {name}", "success")

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
                self.results.apply(plugin.act(name, {}, ctx))
            except Exception as exc:
                log.warning("%s refresh %s failed: %s", plugin.name, name, exc)
                self.results.append_log(f"Could not refresh: {exc}")

    def _launch(self, worker: RunWorker, *, quiet: bool = False, action: bool = False) -> None:
        self._quiet = quiet
        self._action = action
        self.run_bar.set_running(True)
        self.run_started.emit()
        worker.progress.connect(self.run_bar.set_progress)
        worker.log.connect(self.results.append_log)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_failure)
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker
        worker.start()

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
        self.results.apply(result)
        self.run_bar.set_progress(1.0, "")
        self.run_bar.set_status(result.summary or "Done", "success")
        # The run bar describes the Run button, so only a run moves its folder;
        # a row action (classroom's Promote) writes somewhere else entirely.
        if result.files and not self._action:
            self.run_bar.set_output_folder(result.files[0].parent)
        log.info("%s finished: %s", self.plugin.name, result.summary)
        self._last_ok = True

    def _on_failure(self, message: str, is_bug: bool) -> None:
        self.last_result = None
        headline = message.strip().splitlines()[-1] if is_bug else message
        self.run_bar.set_status(headline, "danger")
        self.results.append_log(message)
        (log.error if is_bug else log.warning)("%s failed: %s", self.plugin.name, headline)
        self._last_ok = False
