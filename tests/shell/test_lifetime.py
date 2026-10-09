"""Qt object lifetime around the library index (#49, #40).

Two failure modes, both timing-dependent: a Python wrapper that outlives its
Qt object (the next object allocated at that address comes back as the wrong
type: ``'QStandardItem' object has no attribute 'selectionChanged'``), and a
``QThread`` destroyed while it runs (Qt aborts the process). The tests pin
the window down: no item wrappers, workers stopped before the window goes.

#54 extends the first to every ``QListWidgetItem`` the shell reaches: those
wrappers are safe for a different reason (PySide invalidates them on
``clear()`` and with the list), and the tests here pin that down."""

from __future__ import annotations

import gc
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtGui import QStandardItem
from PySide6.QtWidgets import QApplication, QListWidgetItem
from pytestqt.qtbot import QtBot
from shiboken6 import delete, isValid

from staffroom.core.config import load_config
from staffroom.core.discovery import visible_plugins
from staffroom.core.library.model import Resource
from staffroom.core.library.service import LibraryService
from staffroom.core.panel import Action, ActionTable
from staffroom.core.table import Table
from staffroom.shell.app import _save_screenshot, build_window, parse_args
from staffroom.shell.library.picker import REL_ROLE, ResourcePickerDialog
from staffroom.shell.library.tree import REL_PATH_ROLE, ResourceTreeModel
from staffroom.shell.main_window import MainWindow
from staffroom.shell.sidebar import Sidebar
from staffroom.shell.widgets.action_table import ActionTableWidget
from staffroom.shell.widgets.string_list import StringListEditor

Progress = Callable[[int, int, str], None] | None


def _resource(rel_path: str, **extra: bool) -> Resource:
    name = rel_path.rpartition("/")[2]
    return Resource(rel_path, name, ".py", "python", 10, 1.0, **extra)


def _item_wrappers() -> int:
    return sum(isinstance(o, QStandardItem) for o in gc.get_objects())


def _list_item_wrappers() -> list[QListWidgetItem]:
    return [o for o in gc.get_objects() if isinstance(o, QListWidgetItem)]


@pytest.fixture
def slow_index(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Make every index take about two seconds, reporting progress once per
    10 ms step so a stop request is noticed quickly. Appends the step reached
    to the returned list, so a test can see it did not run to the end."""
    reached: list[int] = []
    real = LibraryService.index

    def index(self: LibraryService, *, full: bool = False, progress: Progress = None):  # type: ignore[no-untyped-def]
        steps = 200
        for i in range(steps):
            reached.append(i)
            if progress is not None:
                progress(i, steps, f"slow/file_{i}.py")  # raises once a stop was asked for
            time.sleep(0.01)
        return real(self, full=full, progress=progress)

    monkeypatch.setattr(LibraryService, "index", index)
    return reached


# ---------------------------------------------------------------- stale wrappers
def test_tree_model_creates_no_item_wrappers(qapp: QApplication) -> None:
    """The tree is built through indexes; no QStandardItem wrapper exists to
    go stale when clear() deletes the items (the cause of #49)."""
    gc.disable()  # a wrapper kept alive by a cycle must show up, not be collected
    try:
        before = _item_wrappers()
        model = ResourceTreeModel()
        model.set_resources(
            [_resource("Python/b.py"), _resource("Python/Sub/c.py"), _resource("a.py", hidden=True)]
        )
        model.set_resources([_resource("Python/d.py", cloud_only=True)])  # clear() + rebuild
        assert _item_wrappers() == before
    finally:
        gc.enable()
    # The tree itself is intact: folders first, then files, roles set.
    assert model.index(0, 0).data() == "Python"
    assert model.index(0, 0, model.index(0, 0)).data() == "d.py  ☁︎"
    assert model.index(0, 0, model.index(0, 0)).data(REL_PATH_ROLE) == "Python/d.py"
    assert model.index(0, 0).data(REL_PATH_ROLE) is None


def test_result_list_rows_are_invalidated_by_clear_and_never_accumulate(
    qtbot: QtBot, service: LibraryService
) -> None:
    """``add_result_row`` leaves one wrapper per row, linked to the list by
    ``addItem``. That is safe where a ``QStandardItem`` was not (#49):
    ``QListWidget.clear()`` invalidates the wrappers before deleting the
    items, so a search that rebuilds the list neither accumulates wrappers nor
    leaves a stale one, and destroying the list releases the rest (#54)."""
    gc.disable()  # a wrapper kept alive by a cycle must show up, not be collected
    try:
        before = _list_item_wrappers()  # held, so their ids stay taken
        base = {id(w) for w in before}

        def fresh() -> list[QListWidgetItem]:
            return [w for w in _list_item_wrappers() if id(w) not in base]

        dialog = ResourcePickerDialog(service, None, None)
        qtbot.addWidget(dialog)
        dialog.search.setText("while")
        results = dialog.results
        rows = results.count()
        assert rows >= 2
        rels = [results.item(i).data(REL_ROLE) for i in range(rows)]  # how the tests read it
        assert "Python/Python_Course/while_loops.py" in rels
        assert len(fresh()) == rows and all(isValid(w) for w in fresh())
        kept = results.item(0)  # what a careless caller might hold across a search

        dialog.search.setText("whil")  # clear() + rebuild
        assert not isValid(kept)  # invalidated, not stale: the guard QStandardItem lacks
        del kept
        assert len(fresh()) == results.count() and all(isValid(w) for w in fresh())
        dialog.search.setText("zzzznothing")  # the "No matches" row
        assert results.count() == 1
        assert len(fresh()) == 1 and all(isValid(w) for w in fresh())

        delete(results)  # the list goes: its linked row wrappers go with it
        assert fresh() == []
    finally:
        gc.enable()


def test_string_list_editor_creates_no_item_wrappers(qtbot: QtBot) -> None:
    """Rows are plain strings (``addItem(str)`` makes no wrapper) and every
    ``item(i)`` wrapper is dropped inside the method that made it, so there is
    nothing for ``clear()`` or ``takeItem()`` to leave stale (#54)."""
    gc.disable()
    try:
        before = len(_list_item_wrappers())
        editor = StringListEditor()
        qtbot.addWidget(editor)
        changes: list[list[str]] = []
        editor.changed.connect(changes.append)
        editor.set_values(["OCR Booklet", "  ", "old", "old"])
        assert editor.values() == ["OCR Booklet", "old"]
        assert editor.remove("old") and editor.add("Scratch")
        editor.list.setCurrentRow(0)
        editor.remove_selected()
        assert editor.values() == ["Scratch"]
        editor.set_values(["a", "b"])  # clear() + rebuild
        assert editor.values() == ["a", "b"]
        assert len(_list_item_wrappers()) == before
        assert changes == [["OCR Booklet"], ["OCR Booklet", "Scratch"], ["Scratch"]]
    finally:
        gc.enable()


def test_sidebar_holds_no_list_items_and_deletes_cleanly(qapp: QApplication) -> None:
    """The sidebar is plain widgets since #89, one row per destination and no
    ``QListWidgetItem`` wrappers to outlive a list (#54); its rows go with it."""
    gc.disable()
    try:
        before = len(_list_item_wrappers())
        plugins = visible_plugins()
        sidebar = Sidebar(plugins)
        assert len(_list_item_wrappers()) == before
        assert sorted(sidebar.tool_names()) == sorted(p.name for p in plugins)
        row = sidebar.item(plugins[-1].name)
        assert row is not None and isValid(row)
        sidebar.set_current(plugins[-1].name)
        assert row.current
        delete(sidebar)
        assert not isValid(row)
    finally:
        gc.enable()


def test_action_table_ignores_a_refresh_after_its_view_is_gone(qtbot: QtBot) -> None:
    spec = ActionTable(key="rows", label="Rows", actions=(Action("open", "Open"),))
    widget = ActionTableWidget(spec)
    qtbot.addWidget(widget)
    widget.set_table(Table(["name"], [["one"]]))
    widget.select_first()
    assert widget.is_alive() and widget.buttons["open"].isEnabled()
    delete(widget.view)  # what teardown does to the Qt side, with the Python object still around
    assert not widget.is_alive()
    widget.set_table(Table(["name"], [["two"]]))  # a queued refresh: must not touch the view
    assert widget.selected_row() is None
    widget._update_buttons()
    assert not widget.buttons["open"].isEnabled()


# ---------------------------------------------------------------- worker lifetime
def test_closing_the_window_stops_a_running_index_and_the_next_launch_finishes_it(
    qtbot: QtBot,
    resources_root: Path,
    tmp_path: Path,
    slow_index: list[int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = load_config()
    config.general.resources_root = str(resources_root)
    library = LibraryService(resources_root, tmp_path / "library.db")
    win = MainWindow(config, library=library)  # never indexed: the first index starts
    qtbot.addWidget(win)
    win.show()
    worker = win.library_page.worker
    assert worker is not None and worker.isRunning()
    indexed: list[object] = []
    win.library_page.indexed.connect(indexed.append)

    started = time.monotonic()
    assert win.close()
    assert not worker.isRunning()
    assert time.monotonic() - started < 1.5  # stopped at the next file, not waited out
    assert len(slow_index) < 200
    assert not indexed and library.last_indexed() is None  # no stamp: the job is not done
    assert win.wait_for_workers()  # idempotent

    # The next launch sees the missing stamp and finishes the index.
    monkeypatch.undo()
    again = MainWindow(config, library=library)
    qtbot.addWidget(again)
    with qtbot.waitSignal(again.library_page.indexed, timeout=10000):
        pass
    assert library.last_indexed() is not None and library.count() > 0
    assert again.resources.status.text() == library.counts().status_line(
        show_hidden=False, sep="\n"
    )


def test_screenshot_run_stops_a_first_index_before_exit(
    qtbot: QtBot,
    qapp: QApplication,
    resources_root: Path,
    tmp_path: Path,
    slow_index: list[int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # app.exit() outside exec() would still mark the thread as quitting, and
    # every later event loop (qtbot.waitSignal in other tests) would return
    # at once. Record the call instead.
    exits: list[int] = []
    monkeypatch.setattr(qapp, "exit", exits.append)
    config = load_config()
    config.general.resources_root = str(resources_root)
    config.save()
    shot = tmp_path / "s.png"
    window = build_window(parse_args(["--screenshot", str(shot)]))
    qtbot.addWidget(window)
    window.show()
    worker = window.library_page.worker
    assert worker is not None and worker.isRunning()

    started = time.monotonic()
    _save_screenshot(qapp, window, shot)
    assert exits == [0] and shot.exists()
    assert not worker.isRunning()
    assert time.monotonic() - started < 1.5
    assert len(slow_index) < 200


def test_screenshot_process_exits_cleanly_while_the_first_index_runs(tmp_path: Path) -> None:
    """The real thing (#40): a fresh home whose folder has never been indexed.
    Enough files that the index is still running when the PNG is saved; before
    the fix the process printed "QThread: Destroyed while thread is still
    running" and exited 134 after writing the file."""
    root = tmp_path / "Resources"
    root.mkdir()
    for i in range(4000):
        (root / f"file_{i}.py").write_text(f"print({i})\n")  # FAKE DATA: numbered files
    home = tmp_path / "home"
    home.mkdir()
    (home / "config.toml").write_text(f'[general]\nresources_root = "{root}"\n')
    shot = tmp_path / "s.png"
    env = {**os.environ, "STAFFROOM_HOME": str(home), "QT_QPA_PLATFORM": "offscreen"}
    proc = subprocess.run(
        [sys.executable, "-m", "staffroom.shell.app", "--screenshot", str(shot)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "Destroyed while thread" not in proc.stderr
    assert shot.exists()
