"""Index the library off the GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from teaching_tools.core.library.service import LibraryService


class IndexWorker(QThread):
    progress = Signal(int, int, str)
    succeeded = Signal(object)  # IndexStats
    failed = Signal(str)

    def __init__(self, service: LibraryService, *, full: bool = False) -> None:
        super().__init__()
        self.service = service
        self.full = full

    def run(self) -> None:
        try:
            stats = self.service.index(
                full=self.full, progress=lambda d, t, rel: self.progress.emit(d, t, rel)
            )
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(stats)
