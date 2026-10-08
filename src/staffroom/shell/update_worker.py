"""Update checks and pulls off the GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from staffroom.core import update


class UpdateWorker(QThread):
    done = Signal(object)  # UpdateStatus

    def __init__(self, *, fetch: bool = True) -> None:
        super().__init__()
        self.fetch = fetch

    def run(self) -> None:
        self.done.emit(update.status(fetch=self.fetch))


class ApplyWorker(QThread):
    done = Signal(str, bool)

    def run(self) -> None:
        try:
            self.done.emit(update.apply(), True)
        except (RuntimeError, OSError) as exc:
            self.done.emit(str(exc), False)
