"""The Resources page in the main area: search results beside the preview."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.config import Config
from staffroom.core.library.model import IndexStats, Kind, withheld_message
from staffroom.core.library.service import LibraryService
from staffroom.core.log import get_logger
from staffroom.shell.library.preview import PreviewPane
from staffroom.shell.library.result_item import add_result_row, no_matches_row
from staffroom.shell.library.worker import IndexWorker
from staffroom.shell.widgets import make_label

log = get_logger(__name__)
REL_ROLE = Qt.ItemDataRole.UserRole


class LibraryPage(QWidget):
    indexed = Signal(object)  # IndexStats
    resource_shown = Signal(str)

    def __init__(
        self, service: LibraryService, config: Config, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.config = config
        self.query = ""
        self.kind: str = "all"
        self.show_hidden = config.general.show_hidden
        self.worker: IndexWorker | None = None
        self._last_stats: IndexStats | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(make_label("Resources", "title"))
        self.subtitle = make_label(str(service.root), "subtitle")
        titles.addWidget(self.subtitle)
        head.addLayout(titles, 1)
        self.index_status = make_label("", "faint")
        head.addWidget(self.index_status, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.hide()
        root.addWidget(self.progress)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.results = QListWidget()
        self.results.setObjectName("ResultList")
        self.results.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results.currentItemChanged.connect(self._on_result)
        self.results.hide()
        self.preview = PreviewPane(service, config.general.theme)
        self.splitter.addWidget(self.results)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setChildrenCollapsible(False)
        root.addWidget(self.splitter, 1)
        self.refresh_status()

    # -- state -----------------------------------------------------------
    def refresh_status(self) -> None:
        last = self.service.last_indexed()
        when = (
            datetime.fromisoformat(last).astimezone().strftime("%d %b %Y, %H:%M")
            if last
            else "never"
        )
        text = f"{self.service.count()} files indexed  ·  last index {when}"
        withheld = self.service.withheld_count()
        if withheld:
            text += f"  ·  {withheld} name only"
        self.index_status.setText(text)
        self.index_status.setToolTip(withheld_message(withheld) if withheld else "")
        self.subtitle.setText(
            str(self.service.root) + ("" if self.service.root_exists else "   (folder not found)")
        )

    def set_theme(self, theme: str) -> None:
        self.preview.set_theme(theme)

    # -- search ----------------------------------------------------------
    def set_query(self, query: str) -> None:
        self.query = query.strip()
        self._run_search()

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        self._run_search()

    def set_show_hidden(self, show: bool) -> None:
        self.show_hidden = show
        self._run_search()

    def _run_search(self) -> None:
        self.results.clear()
        if not self.query:
            self.results.hide()
            return
        kinds: list[Kind] | None = None if self.kind == "all" else [self.kind]  # type: ignore[list-item]
        hits = self.service.search(self.query, kinds=kinds, include_hidden=self.show_hidden)
        for hit in hits:
            add_result_row(self.results, hit, REL_ROLE)
        if not hits:
            no_matches_row(self.results)
        self.results.show()

    def _on_result(self, current: QListWidgetItem | None) -> None:
        if current is None:
            return
        rel = current.data(REL_ROLE)
        if rel:
            self.show_resource(str(rel))

    # -- preview ---------------------------------------------------------
    def show_resource(self, rel_path: str) -> None:
        resource = self.service.get(rel_path)
        if resource is None:
            self.preview.clear()
            return
        self.preview.show_resource(resource)
        self.resource_shown.emit(rel_path)

    # -- indexing --------------------------------------------------------
    def reindex(self, *, full: bool = False) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        if not self.service.root_exists:
            self.index_status.setText(f"Folder not found: {self.service.root}. Set it in Settings.")
            return
        self.progress.setValue(0)
        self.progress.show()
        self.index_status.setText("Indexing…")
        worker = IndexWorker(self.service, full=full)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_indexed)
        worker.failed.connect(self._on_index_failed)
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker
        worker.start()

    def _on_worker_finished(self) -> None:
        if self.worker is not None:
            self.worker.wait()
        if self._last_stats is not None:
            stats, self._last_stats = self._last_stats, None
            self.indexed.emit(stats)

    def _on_progress(self, done: int, total: int, rel: str) -> None:
        if total:
            self.progress.setValue(int(1000 * done / total))
        if rel:
            self.index_status.setText(f"Indexing {done}/{total}: {rel}")

    def _on_indexed(self, stats: IndexStats) -> None:
        self.progress.hide()
        self.refresh_status()
        self._run_search()
        log.info("library: %s", stats.summary())
        self._last_stats = stats

    def _on_index_failed(self, message: str) -> None:
        self.progress.hide()
        self.index_status.setText(f"Indexing failed: {message}")
        log.error("library index failed: %s", message)
