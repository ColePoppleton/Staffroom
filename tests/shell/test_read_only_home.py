"""The launcher opens with a read-only config home (#65). Logging already
falls back to stderr (#60); the Resource Library now opens an in-memory
database when ``<home>/library.db`` cannot be created, says so in the
Resources sidebar, disables Re-index, and leaves every tool usable."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.library.service import library_db_path
from staffroom.shell.main_window import MainWindow

pytestmark = pytest.mark.skipif(os.geteuid() == 0, reason="root is not bound by file modes")

UNAVAILABLE = "Resource Library unavailable: cannot write "


@pytest.fixture
def read_only_home(isolated_home: Path) -> Iterator[Path]:
    isolated_home.mkdir(parents=True)
    isolated_home.chmod(0o500)
    try:
        yield isolated_home
    finally:
        isolated_home.chmod(0o700)


@pytest.fixture
def window(qtbot: QtBot, read_only_home: Path, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")  # never the real folder
    (tmp_path / "resources").mkdir()
    # ``auto_index`` on: the start-up index of a never-indexed folder is the
    # path the real launcher takes, and it must not fire into a database that
    # forgets everything. The update check is skipped because the home cannot
    # hold a config; ``read_only`` is what ``--screenshot`` runs set too.
    config.read_only = True
    win = MainWindow(config, auto_index=True)
    qtbot.addWidget(win)
    win.show()
    return win


def test_window_opens_and_says_the_library_is_unavailable(window: MainWindow) -> None:
    assert not window.library.available
    status = window.resources.status.text()
    assert status.startswith(UNAVAILABLE) and str(library_db_path()) in status
    assert window.resources.status.toolTip()  # the longer explanation
    assert not window.resources.reindex.isEnabled()
    assert UNAVAILABLE in window.library_page.index_status.text()
    assert window.library_page.worker is None  # no start-up index into thin air
    assert not (Path(os.environ["STAFFROOM_HOME"]) / "library.db").exists()


def test_reindex_request_is_refused_quietly(window: MainWindow) -> None:
    window.library_page.reindex(full=True)
    assert window.library_page.worker is None
    assert UNAVAILABLE in window.library_page.index_status.text()


def test_resources_mode_and_search_do_not_crash(window: MainWindow) -> None:
    window.show_library()
    assert window.stack.currentWidget() is window.library_view
    window.focus_library_search()
    window.library_page.set_query("while")
    assert window.library_page.results.count() == 1  # the "no matches" row


def test_tools_still_run(
    window: MainWindow, qtbot: QtBot, example_marks: Path, tmp_path: Path
) -> None:
    window.go_to_tool("hello")
    panel = window.panel_for("hello")
    panel.set_input_path("source", example_marks)
    with qtbot.waitSignal(panel.run_finished, timeout=5000) as blocker:
        panel.start_run()
    assert blocker.args == [True]
    assert (tmp_path / "out" / "marks_10x_totals.csv").exists()


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def test_a_real_launch_with_a_locked_config_does_not_raise(
    qtbot: QtBot, isolated_home: Path, tmp_path: Path
) -> None:
    """Not a ``read_only`` screenshot run: the window tries to remember the
    last tool and the sidebar mode, and ``config.toml`` cannot be written.
    pytest-qt fails the test on any exception raised inside a slot."""
    (tmp_path / "resources").mkdir()
    config = load_config()
    config.general.resources_root = str(tmp_path / "resources")
    config.save()
    config.path.chmod(0o400)
    isolated_home.chmod(0o500)
    records = _Records()  # not caplog: setup_logging stops "staffroom" propagating
    logger = logging.getLogger("staffroom.shell.main_window")
    logger.addHandler(records)
    try:
        win = MainWindow(config, auto_index=False)  # no update check over the network
        qtbot.addWidget(win)
        win.show_library()
        win.sidebar.select("marks")
        win.toggle_theme()
        assert not win.library.available
        saves = [m for m in records.messages if m.startswith("Cannot save ")]
        assert len(saves) == 1, records.messages
        win.wait_for_workers()
    finally:
        logger.removeHandler(records)
        isolated_home.chmod(0o700)
        config.path.chmod(0o600)
