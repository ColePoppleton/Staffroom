"""Renders one tool's PanelSpec with the widget kit and drives its runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

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
    Card,
    EditableTableWidget,
    OptionsFormWidget,
    PathPickerWidget,
    ResourcePickerWidget,
    ResultsArea,
    RunBar,
    TablePreviewWidget,
    TextAreaWidget,
    TextFieldWidget,
    make_label,
)
from staffroom.shell.worker import RunWorker

log = get_logger(__name__)


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
        self.forms: dict[str, OptionsFormWidget] = {}
        self.grids: dict[str, EditableTableWidget] = {}
        self.previews: dict[str, TablePreviewWidget] = {}
        self.worker: RunWorker | None = None
        self.last_result: RunResult | None = None
        self._last_ok = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("PanelContent")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(32, 28, 32, 24)
        self.content_layout.setSpacing(16)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)
        self.scroll_area = scroll

        self._build_header()
        self._build_inputs()
        self.results = ResultsArea(self.spec.outputs)
        self.results.action_requested.connect(self.start_action)
        self.content_layout.addWidget(self.results)
        self.content_layout.addStretch(1)

        footer = QWidget()
        footer.setObjectName("Footer")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(32, 12, 32, 16)
        self.run_bar = RunBar(self.spec.run_label)
        self.run_bar.run_requested.connect(self.start_run)
        footer_layout.addWidget(self.run_bar)
        root.addWidget(footer)
        for picker in self.pickers.values():
            picker.changed.connect(self._show_output_folder)
        for rpicker in self.resource_pickers.values():
            rpicker.changed.connect(self._show_output_folder)
        self._show_output_folder()

    # -- building --------------------------------------------------------
    def _build_header(self) -> None:
        header = QWidget()
        header.setObjectName("Header")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(4)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        title_row.addWidget(make_label(self.spec.title, "title"))
        chip = QLabel(f"v{self.plugin.version}")
        chip.setProperty("role", "chip")
        title_row.addWidget(chip, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch(1)
        layout.addLayout(title_row)
        if self.spec.description:
            layout.addWidget(make_label(self.spec.description, "subtitle", wrap=True))
        self.content_layout.addWidget(header)

    def _build_inputs(self) -> None:
        for spec in self.spec.inputs:
            if isinstance(spec, FilePicker | FolderPicker):
                card = Card(spec.label, spec.help)
                picker = PathPickerWidget(spec)
                card.add(picker)
                self.pickers[spec.key] = picker
            elif isinstance(spec, ResourcePicker):
                card = Card(spec.label, spec.help)
                rpicker = ResourcePickerWidget(spec, self.resources)
                card.add(rpicker)
                self.resource_pickers[spec.key] = rpicker
            elif isinstance(spec, TextField):
                card = Card(spec.label, spec.help)
                field = TextFieldWidget(spec)
                card.add(field)
                self.text_fields[spec.key] = field
            elif isinstance(spec, TextArea):
                card = Card(spec.label, spec.help)
                area = TextAreaWidget(spec)
                card.add(area)
                self.text_areas[spec.key] = area
            elif isinstance(spec, TablePreview):
                card = Card(spec.label)
                preview = TablePreviewWidget(spec)
                card.add(preview)
                self.previews[spec.key] = preview
                self.pickers[spec.source].changed.connect(
                    lambda path, p=preview: self._load_preview(p, path)
                )
            elif isinstance(spec, OptionsForm):
                card = Card(spec.label)
                form = OptionsFormWidget(spec.schema)
                card.add(form)
                self.forms[spec.key] = form
            elif isinstance(spec, EditableTable):
                card = Card(spec.label, spec.help)
                grid = EditableTableWidget(spec)
                card.add(grid)
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
            self.content_layout.addWidget(card)

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

    def _show_output_folder(self, *_: object) -> None:
        """Tell the run bar where the next run will write, before it starts."""
        self.run_bar.set_output_folder(self.output_dir(self.collect_inputs()))

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

    def _launch(self, worker: RunWorker, *, quiet: bool = False) -> None:
        self._quiet = quiet
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
        if result.files:
            self.run_bar.set_output_folder(result.files[0].parent)
        shown = [
            c
            for k, c in self.results.cards.items()
            if (k in result.tables and k not in self.results.action_tables)
            or k in result.images
            or k in result.texts
        ]
        if shown:
            first = shown[0]
            self.content_layout.activate()

            def scroll_to_results() -> None:
                content = self.scroll_area.widget()
                if content is None:
                    return
                top = first.mapTo(content, QPoint(0, 0)).y()
                self.scroll_area.verticalScrollBar().setValue(max(top - 12, 0))

            # The cards were just shown; give the layout a tick to place them.
            # A parented timer dies with the panel, so it can never fire on a
            # destroyed widget (which pytest-qt reports as an error).
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(scroll_to_results)
            timer.start(50)
        log.info("%s finished: %s", self.plugin.name, result.summary)
        self._last_ok = True

    def _on_failure(self, message: str, is_bug: bool) -> None:
        self.last_result = None
        headline = message.strip().splitlines()[-1] if is_bug else message
        self.run_bar.set_status(headline, "danger")
        self.results.append_log(message)
        (log.error if is_bug else log.warning)("%s failed: %s", self.plugin.name, headline)
        self._last_ok = False
