"""Runs a tool off the GUI thread and reports back through signals.

Every shell worker thread derives from :class:`GuiWorker`, which keeps
Python's cyclic garbage collector off the worker thread (#39).

Why: the collector runs on whichever thread happens to allocate when its
threshold trips. While a worker runs that is often the worker (matplotlib
drawing the Marks chart allocates a lot). If the garbage at that moment holds
Qt objects that belong to the GUI thread (a closed panel kept alive by a
reference cycle: widgets, pixmaps, text documents, timers), their C++
destructors run on the worker thread and Qt crashes the whole app with a
segmentation fault, with nothing shown to the teacher.

How: automatic collection is switched off (``gc.disable()``) on the GUI
thread just before the first worker starts, and switched back on, followed by
a full ``gc.collect()``, on the GUI thread once the last one has finished.
While any worker runs, a GUI-thread timer collects every few seconds, so a
long index or tool run does not hoard cyclic garbage. Every collection
therefore happens on the GUI thread, where those destructors are safe. This
is safe in the other direction too: tools never import Qt (the import
contract), so a worker makes no Qt objects for a GUI-thread collection to
free on the wrong thread.

The alternative, collecting before ``start()`` and leaving automatic
collection on, only shrinks the window: garbage made on the GUI thread while
the worker runs (a panel closed mid-run) would still be found by a collection
on the worker. A library that calls ``gc.collect()`` itself would bypass
this; none in a worker's path does (matplotlib stopped doing so in pyplot).
"""

from __future__ import annotations

import gc
import traceback
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal

from staffroom.core.config import Config
from staffroom.core.library.service import ResourceService
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError, ToolPlugin
from staffroom.core.usage import record_run

Job = Callable[[RunContext], RunResult]

#: While any worker runs, the GUI thread collects this often (ms).
COLLECT_EVERY_MS = 5_000


class _GcGate(QObject):
    """Counts running workers. Lives on, and is only touched from, the GUI
    thread: ``hold`` is called by ``GuiWorker.start`` and ``release`` arrives
    through a queued connection from each worker's ``finished``."""

    def __init__(self) -> None:
        super().__init__()
        self.running = 0
        self.was_enabled = True
        self.timer = QTimer(self)
        self.timer.setInterval(COLLECT_EVERY_MS)
        self.timer.timeout.connect(self.collect)

    def hold(self) -> None:
        if self.running == 0:
            self.was_enabled = gc.isenabled()
            gc.disable()
            self.timer.start()
        self.running += 1

    def release(self) -> None:
        if self.running == 0:  # a stray release must not re-enable early
            return
        self.running -= 1
        if self.running == 0:
            self.timer.stop()
            if self.was_enabled:
                gc.enable()
            self.collect()

    def collect(self) -> None:
        gc.collect()


_gate: _GcGate | None = None


def gc_gate() -> _GcGate:
    """The one gate, made on first use (on the GUI thread, by ``start``)."""
    global _gate
    if _gate is None:
        _gate = _GcGate()
    return _gate


def workers_running() -> int:
    """How many shell workers have started and not yet been released."""
    return 0 if _gate is None else _gate.running


class GuiWorker(QThread):
    """A ``QThread`` during whose run no cyclic garbage collection happens
    off the GUI thread. Start it from the GUI thread, as every shell worker
    is. See the module docstring for why."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Queued, to a receiver that outlives every worker, so the release
        # runs on the GUI thread even if this QThread object is gone by then.
        # Connected first, so it runs before the owner's own ``finished``
        # handlers: by the time they report the run, collection is back on.
        self.finished.connect(gc_gate().release, Qt.ConnectionType.QueuedConnection)

    def start(self, priority: QThread.Priority = QThread.Priority.InheritPriority) -> None:
        if self.isRunning():
            return
        gc_gate().hold()
        super().start(priority)


class RunWorker(GuiWorker):
    progress = Signal(float, str)
    log = Signal(str)
    warned = Signal(str)  # a ctx.warn() message (also logged)
    succeeded = Signal(object)  # RunResult
    failed = Signal(str, bool, object)  # message, is_bug, the ToolError (None for a bug)

    def __init__(
        self,
        plugin: ToolPlugin,
        inputs: Inputs,
        config: Config,
        output_dir: Path,
        resources: ResourceService | None = None,
        job: Job | None = None,
    ) -> None:
        super().__init__()
        self.plugin = plugin
        self.inputs = inputs
        self.config = config
        self.output_dir = output_dir
        self.resources = resources
        self.job: Job = job or (lambda ctx: plugin.run(inputs, ctx))
        self.job_is_run = job is None

    def run(self) -> None:
        ctx = RunContext(
            config=self.config,
            output_dir=self.output_dir,
            progress=lambda f, m: self.progress.emit(f, m),
            log=lambda m: self.log.emit(m),
            warned=lambda m: self.warned.emit(m),
            resources=self.resources,
        )
        try:
            result = self.job(ctx)
            if self.job_is_run:
                record_run(self.plugin.name)
        except ToolError as exc:
            # A fresh copy, never raised: the raised one's traceback would keep
            # this run's frames (and this worker) alive in a reference cycle.
            detail = ToolError(
                str(exc),
                next_step=exc.next_step,
                input_key=exc.input_key,
                input_hint=exc.input_hint,
            )
            self.failed.emit(str(exc), False, detail)
        except Exception:
            self.failed.emit(traceback.format_exc(), True, None)
        else:
            self.succeeded.emit(result)
