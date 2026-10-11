"""No cyclic garbage collection on a worker thread (#39).

Python's collector runs on whichever thread allocates when its threshold
trips. During a run that was often the worker (matplotlib drawing the Marks
chart), and when the garbage held Qt objects of the GUI thread (a closed
panel in a reference cycle) their C++ destructors ran on the worker and the
app died with a segmentation fault. Every shell worker is a ``GuiWorker``:
automatic collection is off while any of them runs and the GUI thread
collects instead. These tests pin that down deterministically: a low
threshold or a burst of allocations makes a worker-thread collection certain
if the guard ever goes, and the subprocess test is the crash itself."""

from __future__ import annotations

import gc
import os
import re
import subprocess
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext, RunResult
from staffroom.shell import worker as worker_module
from staffroom.shell.library.worker import IndexWorker
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.update_worker import ApplyWorker, ReleaseWorker, UpdateWorker
from staffroom.shell.worker import GuiWorker, RunWorker, workers_running

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


@pytest.fixture
def collections() -> Iterator[list[str]]:
    """The thread of every collection that starts while the test runs."""
    seen: list[str] = []

    def record(phase: str, info: dict[str, Any]) -> None:
        if phase == "start":
            seen.append(threading.current_thread().name)

    gc.callbacks.append(record)
    try:
        yield seen
    finally:
        gc.callbacks.remove(record)


@pytest.fixture
def low_threshold() -> Iterator[None]:
    """A collection every hundred allocations: one on the worker is certain
    unless automatic collection is off there."""
    before = gc.get_threshold()
    gc.set_threshold(100, 10, 10)
    try:
        yield
    finally:
        gc.set_threshold(*before)


def churn(n: int = 300_000) -> None:
    """Allocate container objects in cycles, as a busy tool run does."""
    for _ in range(n):
        node: list[object] = []
        node.append(node)


def run_worker(qtbot: QtBot, tmp_path: Path, job: Any) -> RunWorker:
    worker = RunWorker(None, {}, load_config(), tmp_path, job=job)  # type: ignore[arg-type]
    with qtbot.waitSignal(worker.finished, timeout=30000):
        worker.start()
    worker.wait()
    QApplication.processEvents()  # the queued release
    return worker


def test_no_automatic_collection_on_a_run_worker(
    qtbot: QtBot, tmp_path: Path, collections: list[str], low_threshold: None
) -> None:
    inside: list[bool] = []

    def job(ctx: RunContext) -> RunResult:
        inside.append(gc.isenabled())
        churn()
        return RunResult(summary="done")

    assert gc.isenabled()
    run_worker(qtbot, tmp_path, job)
    assert inside == [False]
    assert gc.isenabled() and workers_running() == 0
    main = threading.main_thread().name
    assert collections, "the release collects on the GUI thread"
    assert set(collections) == {main}, collections


def test_the_marks_chart_run_collects_only_on_the_gui_thread(
    qtbot: QtBot, tmp_path: Path, collections: list[str], low_threshold: None
) -> None:
    """Where the crash was seen: matplotlib allocating in ``add_subplot``."""
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False, first_run=False)
    qtbot.addWidget(win)
    win.show()
    win.sidebar.select("marks")
    panel = win.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == "marks"
    panel.set_input_path("marks", EXAMPLES / "marks_10x_max.csv")
    collections.clear()
    with qtbot.waitSignal(panel.run_finished, timeout=30000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.strip.text()
    assert (tmp_path / "out").exists()
    assert gc.isenabled() and workers_running() == 0
    assert set(collections) <= {threading.main_thread().name}, collections


def test_collection_stays_off_until_the_last_worker_finishes(qtbot: QtBot, tmp_path: Path) -> None:
    gates = [threading.Event(), threading.Event()]

    def blocked(i: int) -> Any:
        def job(ctx: RunContext) -> RunResult:
            gates[i].wait(10)
            return RunResult()

        return job

    first = RunWorker(None, {}, load_config(), tmp_path, job=blocked(0))  # type: ignore[arg-type]
    second = RunWorker(None, {}, load_config(), tmp_path, job=blocked(1))  # type: ignore[arg-type]
    first.start()
    second.start()
    first.start()  # already running: no second hold
    assert workers_running() == 2 and not gc.isenabled()

    with qtbot.waitSignal(first.finished, timeout=10000):
        gates[0].set()
    first.wait()
    QApplication.processEvents()
    assert workers_running() == 1 and not gc.isenabled()

    with qtbot.waitSignal(second.finished, timeout=10000):
        gates[1].set()
    second.wait()
    QApplication.processEvents()
    assert workers_running() == 0 and gc.isenabled()


def test_a_collector_left_off_by_someone_else_stays_off(qtbot: QtBot, tmp_path: Path) -> None:
    gc.disable()
    try:
        run_worker(qtbot, tmp_path, lambda ctx: RunResult())
        assert not gc.isenabled()
    finally:
        gc.enable()


def test_long_runs_are_collected_on_the_gui_thread_meanwhile(
    qtbot: QtBot, tmp_path: Path, collections: list[str]
) -> None:
    """A long index must not hoard cyclic garbage until it ends."""
    gate = worker_module.gc_gate()
    gate.timer.setInterval(20)  # restored in finally
    release = threading.Event()

    def job(ctx: RunContext) -> RunResult:
        release.wait(10)
        return RunResult()

    worker = RunWorker(None, {}, load_config(), tmp_path, job=job)  # type: ignore[arg-type]
    try:
        worker.start()
        collections.clear()
        qtbot.waitUntil(lambda: len(collections) >= 2, timeout=5000)
        assert worker.isRunning()
        assert set(collections) == {threading.main_thread().name}
    finally:
        release.set()
        worker.wait()
        QApplication.processEvents()
        gate.timer.setInterval(worker_module.COLLECT_EVERY_MS)
    assert gc.isenabled()


def test_every_shell_worker_is_guarded() -> None:
    for cls in (RunWorker, IndexWorker, UpdateWorker, ReleaseWorker, ApplyWorker):
        assert issubclass(cls, GuiWorker), cls.__name__
    # A new worker must derive from GuiWorker too, not straight from QThread.
    shell = Path(worker_module.__file__).parent
    direct = [
        f"{path.relative_to(shell)}:{n}"
        for path in shell.rglob("*.py")
        for n, line in enumerate(path.read_text().splitlines(), 1)
        if re.match(r"\s*class \w+\(.*\bQThread\b", line)
    ]
    assert direct == ["worker.py:" + str(_line_of_gui_worker())], direct


def _line_of_gui_worker() -> int:
    lines = Path(worker_module.__file__).read_text().splitlines()
    return next(n for n, line in enumerate(lines, 1) if line.startswith("class GuiWorker("))


CRASH = """
import gc, sys, threading
from pathlib import Path
from PySide6.QtGui import QColor, QPainter, QPixmap, QTextDocument
from PySide6.QtWidgets import (
    QApplication, QLabel, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)
from staffroom.core.config import load_config
from staffroom.core.plugin import RunResult
from staffroom.shell.worker import RunWorker

app = QApplication(sys.argv)
freed_on = []


class Closed(QWidget):
    # A closed panel kept alive only by a reference cycle.
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        self.pix = QPixmap(200, 150)
        self.pix.fill(QColor("white"))
        p = QPainter(self.pix); p.drawText(10, 10, "chart"); p.end()
        label = QLabel(); label.setPixmap(self.pix); lay.addWidget(label)
        self.notes = QTextBrowser(); self.notes.setHtml("<h1>notes</h1>" * 20)
        lay.addWidget(self.notes)
        self.table = QTableWidget(10, 4)
        for r in range(10):
            for c in range(4):
                self.table.setItem(r, c, QTableWidgetItem(f"{r},{c}"))
        lay.addWidget(self.table)
        self.doc = QTextDocument(); self.doc.setHtml("<b>doc</b>")
        self.again = lambda: self.update()  # the cycle

    def __del__(self):
        freed_on.append(threading.current_thread().name)


gc.disable()  # make the garbage without the GUI thread collecting it
for _ in range(30):
    w = Closed(); w.resize(500, 400); w.show(); app.processEvents(); w.grab(); w.close()
    del w
gc.set_threshold(100_000)  # nothing on the GUI thread trips it before the run starts
gc.enable()


def job(ctx):
    for _ in range(400_000):  # a busy run trips the threshold here, on the worker
        node = []
        node.append(node)
    return RunResult()


worker = RunWorker(None, {}, load_config(), Path(sys.argv[1]), job=job)
worker.start()
worker.wait()  # the GUI thread blocked meanwhile: the release arrives below
app.processEvents()
gc.collect()
app.processEvents()
print("freed on:", sorted(set(freed_on)), len(freed_on), flush=True)
"""


def test_gui_garbage_left_by_a_closed_panel_never_crashes_a_run(tmp_path: Path) -> None:
    """The crash itself, in a child process so a regression fails this test
    instead of killing the suite. Before the fix the child segfaulted every
    time (5 of 5): the worker's allocations tripped a collection that freed
    the GUI-thread widgets, pixmaps and text documents on the worker (Qt
    printed "QBasicTimer::stop: Failed. Possibly trying to stop from a
    different thread"), and the next event the GUI thread processed crashed."""
    script = tmp_path / "crash.py"
    script.write_text(CRASH)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    proc = subprocess.run(
        [sys.executable, "-X", "faulthandler", str(script), str(tmp_path)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr[-3000:]
    assert "freed on: ['MainThread'] 30" in proc.stdout, proc.stdout + proc.stderr[-2000:]
