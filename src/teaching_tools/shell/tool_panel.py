"""Renders one tool's PanelSpec with the widget kit and drives its runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from teaching_tools.core.config import Config
from teaching_tools.core.csvio import read_table
from teaching_tools.core.log import get_logger
from teaching_tools.core.panel import (
    EditableTable,
    FilePicker,
    FolderPicker,
    OptionsForm,
    PanelSpec,
    TablePreview,
)
from teaching_tools.core.paths import default_output_dir
from teaching_tools.core.plugin import RunResult, ToolPlugin
from teaching_tools.shell.widgets import (
    Card,
    EditableTableWidget,
    OptionsFormWidget,
    PathPickerWidget,
    ResultsArea,
    RunBar,
    TablePreviewWidget,
    make_label,
)
from teaching_tools.shell.worker import RunWorker

log = get_logger(__name__)


class ToolPanel(QWidget):
    run_started = Signal()
    run_finished = Signal(bool)  # ok

    def __init__(self, plugin: ToolPlugin, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.plugin = plugin
        self.config = config
        self.spec: PanelSpec = plugin.panel_spec()
        self.pickers: dict[str, PathPickerWidget] = {}
        self.forms: dict[str, OptionsFormWidget] = {}
        self.grids: dict[str, EditableTableWidget] = {}
        self.previews: dict[str, TablePreviewWidget] = {}
        self.worker: RunWorker | None = None
        self.last_result: RunResult | None = None

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
        except Exception as exc:
            log.warning("could not preview %s: %s", path, exc)
            preview.set_error(f"Could not read {path.name}: {exc}")

    # -- values ----------------------------------------------------------
    def collect_inputs(self) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for key, picker in self.pickers.items():
            values[key] = picker.value()
        for key, form in self.forms.items():
            values[key] = form.value()
        for key, grid in self.grids.items():
            values[key] = grid.value()
        return values

    def set_input_path(self, key: str, path: Path | None) -> None:
        self.pickers[key].set_path(path)

    def first_file_key(self) -> str | None:
        for spec in self.spec.inputs:
            if isinstance(spec, FilePicker):
                return spec.key
        return None

    def output_dir(self, inputs: dict[str, Any]) -> Path:
        first = self.first_file_key()
        anchor = inputs.get(first) if first else None
        return default_output_dir(anchor, self.config.general.output_dir)

    # -- running ---------------------------------------------------------
    def start_run(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        inputs = self.collect_inputs()
        missing = [
            s.label
            for s in self.spec.inputs
            if isinstance(s, FilePicker | FolderPicker) and s.required and inputs.get(s.key) is None
        ]
        if missing:
            self.run_bar.set_status(f"Choose: {', '.join(missing)}", "danger")
            return
        self.results.clear()
        self.run_bar.set_running(True)
        self.run_started.emit()
        log.info("running %s", self.plugin.name)
        worker = RunWorker(self.plugin, inputs, self.config, self.output_dir(inputs))
        worker.progress.connect(self.run_bar.set_progress)
        worker.log.connect(self.results.append_log)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_failure)
        worker.finished.connect(lambda: self.run_bar.set_running(False))
        self.worker = worker
        worker.start()

    def _on_success(self, result: RunResult) -> None:
        self.last_result = result
        self.results.apply(result)
        self.run_bar.set_progress(1.0, "")
        self.run_bar.set_status(result.summary or "Done", "success")
        if result.files:
            self.run_bar.set_output_folder(result.files[0].parent)
        shown = [
            c for k, c in self.results.cards.items() if k in result.tables or k in result.images
        ]
        if shown:
            first = shown[0]
            # Let the layout place the freshly shown card before scrolling to it.
            QTimer.singleShot(
                0, lambda: self.scroll_area.verticalScrollBar().setValue(first.y() - 12)
            )
        log.info("%s finished: %s", self.plugin.name, result.summary)
        self.run_finished.emit(True)

    def _on_failure(self, message: str, is_bug: bool) -> None:
        self.last_result = None
        headline = message.strip().splitlines()[-1] if is_bug else message
        self.run_bar.set_status(headline, "danger")
        self.results.append_log(message)
        (log.error if is_bug else log.warning)("%s failed: %s", self.plugin.name, headline)
        self.run_finished.emit(False)
