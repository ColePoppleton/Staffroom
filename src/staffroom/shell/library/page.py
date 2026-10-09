"""The Library: one page. A header line (where the folder is, what is in the
index), then two columns: the search box, filters and folder tree (or the
search results in its place) on the left, the chosen file's preview on the
right with its tags and the use bar over the file itself."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidgetItem,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.config import Config
from staffroom.core.library.model import IndexStats, Kind, LibraryCounts, withheld_message
from staffroom.core.library.service import LibraryService
from staffroom.core.log import get_logger
from staffroom.shell.library.preview import PreviewPane
from staffroom.shell.library.result_item import add_result_row, no_matches_row
from staffroom.shell.library.sidebar_panel import ResourcesPanel
from staffroom.shell.library.worker import IndexWorker
from staffroom.shell.widgets import make_label
from staffroom.shell.widgets.elided_label import ElidedLabel

log = get_logger(__name__)
REL_ROLE = Qt.ItemDataRole.UserRole
COLUMN_WIDTH = 262


def short_path(path: Path) -> str:
    """``~/Department/Resources`` for a folder under home; others in full."""
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(path)


class StatusLabel(ElidedLabel):
    """Asks for its whole text's width but gives way (eliding in the middle)
    when the window is narrow, so a long status never sets the window's
    minimum width (#103)."""

    def __init__(self) -> None:
        # The tooltip is the longer explanation the page sets, not the text.
        super().__init__(mode=Qt.TextElideMode.ElideMiddle, auto_tooltip=False)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def setText(self, text: str) -> None:  # noqa: N802
        super().setText(text)
        self.updateGeometry()

    def sizeHint(self) -> QSize:  # noqa: N802
        width = self.fontMetrics().horizontalAdvance(self.text()) + 6
        return QSize(width, super().sizeHint().height())


def counts_detail(counts: LibraryCounts) -> str:
    """The tooltip behind a terse count: the long form, and why some files
    are name only. Shared by the sidebar footer and the Resources header."""
    detail = counts.describe()
    if counts.name_only:
        detail += "\n" + withheld_message(counts.name_only)
    return detail


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
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- one header line: Library, the folder, what is in the index
        header = QWidget()
        header.setObjectName("PanelHeader")
        header.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        head = QHBoxLayout(header)
        head.setContentsMargins(28, 16, 28, 12)
        head.setSpacing(14)
        head.addWidget(make_label("Library", "title"), 0, Qt.AlignmentFlag.AlignBaseline)
        # The folder is elided in the middle, whole in the tooltip: a deep
        # path never widens the window past its minimum (#103).
        self.subtitle = ElidedLabel(mode=Qt.TextElideMode.ElideMiddle, auto_tooltip=False)
        self.subtitle.setProperty("role", "subtitle")
        head.addWidget(self.subtitle, 1, Qt.AlignmentFlag.AlignBaseline)
        self.index_status = StatusLabel()
        self.index_status.setProperty("role", "faint")
        head.addWidget(self.index_status, 0, Qt.AlignmentFlag.AlignBaseline)
        root.addWidget(header)

        self.progress = QProgressBar()
        self.progress.setObjectName("RunProgress")
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.hide()
        root.addWidget(self.progress)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        root.addLayout(body, 1)

        # -- the left column: search, filters, the tree or the results
        self.column = ResourcesPanel()
        column = QWidget()
        column.setObjectName("LibraryColumn")
        column.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        column.setFixedWidth(COLUMN_WIDTH)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 14, 0, 4)
        column_layout.addWidget(self.column)
        body.addWidget(column)
        self.results = self.column.results
        self.results.currentItemChanged.connect(self._on_result)

        # -- the preview, with the use bar
        self.preview = PreviewPane(service, config.general.theme)
        preview_host = QWidget()
        preview_layout = QVBoxLayout(preview_host)
        preview_layout.setContentsMargins(24, 18, 24, 18)
        preview_layout.addWidget(self.preview)
        body.addWidget(preview_host, 1)
        self.refresh_status()

    # -- state -----------------------------------------------------------
    def refresh_status(self) -> None:
        last = self.service.last_indexed()
        when = (
            datetime.fromisoformat(last).astimezone().strftime("%d %b %Y, %H:%M")
            if last
            else "never"
        )
        # The same line the sidebar footer shows, from the same tally (#30).
        counts = self.service.counts()
        if self.service.unavailable_reason is not None:  # read-only home (#65)
            self.index_status.setText(self.service.unavailable_reason)
            self.index_status.setToolTip(self.service.unavailable_detail())
        else:
            self.index_status.setText(
                f"{counts.status_line(show_hidden=self.show_hidden)}  ·  last index {when}"
            )
            self.index_status.setToolTip(counts_detail(counts))
        if not self.service.root_set:
            self.subtitle.setText("No folder chosen yet: set it in Settings")
            self.subtitle.setToolTip("")
        else:
            self.subtitle.setText(
                short_path(self.service.root)
                + ("" if self.service.root_exists else "   (folder not found)")
            )
            self.subtitle.setToolTip(str(self.service.root))

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
        self.refresh_status()
        self._run_search()

    def _run_search(self) -> None:
        self.results.clear()  # invalidates the row wrappers too, unlike QStandardItemModel (#54)
        if not self.query:
            self.column.show_results(False)
            return
        kinds: list[Kind] | None = None if self.kind == "all" else [self.kind]  # type: ignore[list-item]
        hits = self.service.search(self.query, kinds=kinds, include_hidden=self.show_hidden)
        for hit in hits:
            add_result_row(self.results, hit, REL_ROLE)
        if not hits:
            no_matches_row(self.results)
        self.column.show_results(True)

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
        if self.service.unavailable_reason is not None:
            # Nowhere to keep an index (#65); the reason is already logged once.
            self.refresh_status()
            return
        if not self.service.root_exists:
            # The folder itself is in the header, elided (#103).
            self.index_status.setText("Folder not found: set it in Settings.")
            return
        self.progress.setValue(0)
        self.progress.show()
        self.index_status.setText("Indexing…")
        worker = IndexWorker(self.service, full=full)
        worker.progress.connect(self._on_progress)
        worker.succeeded.connect(self._on_indexed)
        worker.failed.connect(self._on_index_failed)
        worker.cancelled.connect(self._on_index_cancelled)
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker
        worker.start()

    def stop_index(self, timeout_ms: int = 10_000) -> bool:
        """Stop a running index at the next file and wait for its thread.
        Called before the window goes away: a ``QThread`` destroyed while
        running aborts the whole process. Returns True when no index thread
        is running afterwards; the indexer keeps what it had done so far and
        the next launch finishes the job (no ``last_indexed`` is stamped)."""
        worker = self.worker
        if worker is None or not worker.isRunning():
            return True
        worker.requestInterruption()
        stopped = worker.wait(timeout_ms)
        if not stopped:
            log.error("library index did not stop within %d ms", timeout_ms)
        return stopped

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

    def _on_index_cancelled(self) -> None:
        self.progress.hide()
        self.refresh_status()
        log.info("library index stopped early; it resumes on the next launch")

    def _on_index_failed(self, message: str) -> None:
        self.progress.hide()
        self.index_status.setText(f"Indexing failed: {message}")
        log.error("library index failed: %s", message)
