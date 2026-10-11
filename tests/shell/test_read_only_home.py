"""The launcher opens with a read-only config home (#65). Logging already
falls back to stderr (#60); the Resource Library now opens an in-memory
database when ``<home>/library.db`` cannot be created, says so in the
Resources sidebar, disables Re-index, and leaves every tool usable. Saving
the config (window choices, Settings, a marks preset) never raises: the change
lasts for the session and the teacher is told (#74)."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from staffroom.core.config import Config, load_config
from staffroom.core.library.service import library_db_path
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets import CompactTableWidget

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
    assert window.stack.currentWidget() is window.library_page
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
    assert (tmp_path / "out" / "marks_10x_summary.csv").exists()


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def config_records() -> Iterator[_Records]:
    records = _Records()  # not caplog: setup_logging stops "staffroom" propagating
    logger = logging.getLogger("staffroom.core.config")
    logger.addHandler(records)
    try:
        yield records
    finally:
        logger.removeHandler(records)


@pytest.fixture
def locked_config(isolated_home: Path, tmp_path: Path) -> Iterator[Config]:
    """Not a ``read_only`` screenshot run: ``config.toml`` exists at ``0o400``
    in a ``0o500`` home, so every save really fails. Restored on teardown."""
    (tmp_path / "resources").mkdir()
    config = load_config()
    config.general.resources_root = str(tmp_path / "resources")
    config.general.output_dir = str(tmp_path / "out")
    config.save()
    config.path.chmod(0o400)
    isolated_home.chmod(0o500)
    try:
        yield config
    finally:
        isolated_home.chmod(0o700)
        config.path.chmod(0o600)


@pytest.fixture
def locked_window(
    qtbot: QtBot, locked_config: Config, config_records: _Records
) -> Iterator[MainWindow]:
    win = MainWindow(locked_config, auto_index=False)  # no update check over the network
    qtbot.addWidget(win)
    win.show()
    yield win
    win.wait_for_workers()


def _saves(records: _Records) -> list[str]:
    return [m for m in records.messages if m.startswith("Cannot save ")]


def test_a_real_launch_with_a_locked_config_does_not_raise(
    locked_window: MainWindow, config_records: _Records
) -> None:
    """The window tries to remember the last tool and the sidebar mode, and
    ``config.toml`` cannot be written. pytest-qt fails the test on any
    exception raised inside a slot."""
    win = locked_window
    win.show_library()
    win.sidebar.select("marks")
    win.toggle_theme()
    assert not win.library.available
    assert len(_saves(config_records)) == 1, config_records.messages
    assert win.settings.save_notice.isVisibleTo(win.settings)


def test_settings_changes_apply_for_the_session_and_say_so(
    locked_window: MainWindow, config_records: _Records, tmp_path: Path
) -> None:
    """Every Settings slot that saves: no traceback, the change applies in
    memory, one warning in the log, one line on the page (#74)."""
    win, config = locked_window, locked_window.config
    page = win.settings
    win.show_settings()
    page.theme.setCurrentText("light" if config.general.theme == "dark" else "dark")
    page.board.setCurrentIndex(page.board.findData("aqa"))
    page.house_header.setText("Example High School")
    page.house_header.editingFinished.emit()
    page.editor_preset.setCurrentText("Custom")
    page.editor_command.setText("open -a IDLE {file}")
    page.editor_command.editingFinished.emit()
    page.log_level.setCurrentText("DEBUG")
    page._on_output_dir(tmp_path / "elsewhere")
    page._on_sessions_root(tmp_path / "sessions")
    page._on_library_exclude(["Pupil work"])
    assert config.general.board == "aqa"
    assert config.general.house_header == "Example High School"
    assert config.general.editor_command == "open -a IDLE {file}"
    assert config.general.log_level == "DEBUG"
    assert config.general.output_dir == str(tmp_path / "elsewhere")
    assert config.general.sessions_root == str(tmp_path / "sessions")
    assert config.general.library_exclude == ["Pupil work"]
    assert page.save_notice.isVisibleTo(page)
    assert page.save_notice.text() == (
        f"Settings could not be saved: {config.path} is read-only. Changes last until you quit."
    )
    assert len(_saves(config_records)) == 1, config_records.messages
    assert load_config().general.board == "ocr"  # nothing reached the file


def test_the_notice_clears_once_a_save_works(
    locked_window: MainWindow, isolated_home: Path
) -> None:
    page, config = locked_window.settings, locked_window.config
    page.log_level.setCurrentText("WARNING")
    assert page.save_notice.isVisibleTo(page)
    isolated_home.chmod(0o700)  # the technician unlocks the folder
    config.path.chmod(0o600)
    page.log_level.setCurrentText("ERROR")
    assert not page.save_notice.isVisibleTo(page)
    assert load_config().general.log_level == "ERROR"


def test_saving_a_marks_preset_shows_a_message_not_a_traceback(
    locked_window: MainWindow, config_records: _Records
) -> None:
    locked_window.sidebar.select("marks")
    panel = locked_window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == "marks"
    grid = panel.grids["boundaries"]
    assert isinstance(grid, CompactTableWidget)
    grid.add_preset("Custom A", grid.value().rows)
    grid.preset_saved.emit("Custom A", grid.value())
    text = panel.strip.text()
    assert text == (
        f"Preset 'Custom A' could not be saved: {locked_window.config.path} is read-only. "
        "You can use it until you quit."
    )
    assert panel.strip.state == "danger"
    # The whole message is on screen, path and all, not cut after two lines (#121).
    assert "…" not in QLabel.text(panel.strip.message)
    assert not panel.strip.message.toolTip()
    assert "Traceback" not in panel.results.log_view.toPlainText()
    # Still in the list, and in the session's config, until the app quits.
    assert grid.preset_combo.findText("Custom A") >= 0
    assert "Custom A" in locked_window.config.tool("marks")["presets"]
    assert len(_saves(config_records)) == 1, config_records.messages
