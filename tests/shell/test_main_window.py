"""End-to-end through the launcher: open hello, load the example, run it,
see the results table fill and the output file appear."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")  # never the real folder
    win = MainWindow(config, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    win.sidebar.select("hello")
    return win


def test_sidebar_lists_hello_and_opens_its_panel(window: MainWindow) -> None:
    assert window.sidebar.list.count() >= 1
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel)
    assert panel.plugin.name == "hello"
    assert panel.spec.title == "Hello"
    assert window.config.general.last_tool == "hello"


def test_preview_fills_when_file_chosen(window: MainWindow, example_marks: Path) -> None:
    panel = window.panel_for("hello")
    panel.set_input_path("source", example_marks)
    preview = panel.previews["preview"]
    assert preview.model.rowCount() == 10
    assert preview.model.columnCount() == 6
    assert preview.stack.currentWidget() is preview.view
    assert "fake data" in preview.caption.text()


def test_run_requires_a_file(window: MainWindow) -> None:
    panel = window.panel_for("hello")
    panel.start_run()
    assert panel.worker is None
    assert "Fill in" in panel.run_bar.status.text()


def test_run_hello_end_to_end(
    window: MainWindow, qtbot: QtBot, example_marks: Path, tmp_path: Path
) -> None:
    panel = window.panel_for("hello")
    panel.set_input_path("source", example_marks)
    with qtbot.waitSignal(panel.run_finished, timeout=5000) as blocker:
        panel.start_run()
    assert blocker.args == [True]
    model, _view, caption = panel.results.tables["result"]
    assert model.columnCount() == 7
    assert model.headerData(6, Qt.Orientation.Horizontal) == "Total"
    assert "10 rows" in caption.text()
    assert (tmp_path / "out" / "marks_10x_totals.csv").exists()
    assert panel.run_bar.open_folder.isVisible()


def test_run_failure_is_reported_not_raised(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("mark\n9\n")  # no q-columns
    panel = window.panel_for("hello")
    panel.set_input_path("source", bad)
    with qtbot.waitSignal(panel.run_finished, timeout=5000) as blocker:
        panel.start_run()
    assert blocker.args == [False]
    assert "No question columns" in panel.run_bar.status.text()


def test_preview_drops_identifier_columns(window: MainWindow, tmp_path: Path) -> None:
    src = tmp_path / "scripts.csv"
    src.write_text("Name,q1\nx,3\n")
    panel = window.panel_for("hello")
    panel.set_input_path("source", src)
    preview = panel.previews["preview"]
    assert preview.model.columnCount() == 1
    assert "dropped identifier columns: Name" in preview.caption.text()
    assert "Name" in panel.results.log_view.toPlainText()


def test_theme_toggle_persists(window: MainWindow) -> None:
    assert window.config.general.theme == "dark"
    window.toggle_theme()
    assert window.config.general.theme == "light"
    assert load_config().general.theme == "light"
    window.toggle_theme()
    assert window.config.general.theme == "dark"


def test_settings_page_shows(window: MainWindow) -> None:
    window.sidebar.settings_button.click()
    assert window.stack.currentWidget() is window.settings
