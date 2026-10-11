"""Index the library off the GUI thread."""

from __future__ import annotations

from PySide6.QtCore import Signal

from staffroom.core.library.service import LibraryService
from staffroom.shell.worker import GuiWorker


class IndexInterruptedError(Exception):
    """Raised inside the worker's progress callback once a stop was requested."""


class IndexWorker(GuiWorker):
    """``requestInterruption()`` stops the run at the next file: what was
    indexed so far is kept (the indexer commits in ``finally``) but no
    ``last_indexed`` stamp is written, so the next launch finishes the job."""

    progress = Signal(int, int, str)
    succeeded = Signal(object)  # IndexStats
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, service: LibraryService, *, full: bool = False) -> None:
        super().__init__()
        self.service = service
        self.full = full

    def _report(self, done: int, total: int, rel: str) -> None:
        if self.isInterruptionRequested():
            raise IndexInterruptedError
        self.progress.emit(done, total, rel)

    def run(self) -> None:
        try:
            stats = self.service.index(full=self.full, progress=self._report)
        except IndexInterruptedError:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(stats)
