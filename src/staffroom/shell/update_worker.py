"""Update checks and pulls off the GUI thread."""

from __future__ import annotations

from PySide6.QtCore import Signal

from staffroom.core import update
from staffroom.shell.worker import GuiWorker


class UpdateWorker(GuiWorker):
    done = Signal(object)  # UpdateStatus

    def __init__(self, *, fetch: bool = True) -> None:
        super().__init__()
        self.fetch = fetch

    def run(self) -> None:
        self.done.emit(update.status(fetch=self.fetch))


class ReleaseWorker(GuiWorker):
    """Ask GitHub for the newest release (an installed copy, #11). Never git."""

    done = Signal(object)  # ReleaseCheck

    def run(self) -> None:
        self.done.emit(update.check_latest_release())


class ApplyWorker(GuiWorker):
    done = Signal(str, bool)

    def run(self) -> None:
        try:
            self.done.emit(update.apply(), True)
        except (RuntimeError, OSError) as exc:
            self.done.emit(str(exc), False)
