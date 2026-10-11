from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.paths import examples_dir
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    return win


def test_quiz_panel_exports_kahoot(window: MainWindow, qtbot: QtBot, tmp_path: Path) -> None:
    window.sidebar.select("quiz")
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel)
    panel.set_input_path("source", examples_dir() / "question_bank.md")
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.strip.text()
    assert panel.results.tables["chosen"][0].rowCount() == 10
    assert "Question - max 120 characters" in panel.results.text_views["paste"].toPlainText()
    assert (tmp_path / "out" / "question_bank_kahoot_s1.xlsx").exists()


def _quiz(window: MainWindow) -> ToolPanel:
    window.sidebar.select("quiz")
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel)
    return panel


def test_taught_log_shows_only_in_retrieval_mode(window: MainWindow) -> None:
    """#123: the picker is a whole input group outside the options form; it
    hides, with the hairline over it, until Retrieval mode is ticked."""
    panel = _quiz(window)
    group, divider = panel.groups["taught_log"], panel.dividers["taught_log"]
    form = panel.forms["options"]
    assert group.isHidden() and divider.isHidden()
    assert panel.hidden_inputs() == {"taught_log"}
    form.set_field("retrieval", True)
    assert not group.isHidden() and not divider.isHidden()
    assert panel.hidden_inputs() == set()
    form.set_field("retrieval", False)
    assert group.isHidden() and divider.isHidden()


def test_a_hidden_taught_log_is_not_handed_to_the_tool(window: MainWindow) -> None:
    panel = _quiz(window)
    form = panel.forms["options"]
    log_path = examples_dir() / "taught_log.csv"
    form.set_field("retrieval", True)
    panel.set_input_path("taught_log", log_path)
    assert panel.collect_inputs()["taught_log"] == log_path
    form.set_field("retrieval", False)
    assert panel.collect_inputs()["taught_log"] is None
    assert panel.pickers["taught_log"].value() == log_path  # kept for when it comes back
    form.set_field("retrieval", True)
    assert panel.collect_inputs()["taught_log"] == log_path


def test_retrieval_mode_asks_for_the_log_only_while_it_shows(
    window: MainWindow, qtbot: QtBot
) -> None:
    panel = _quiz(window)
    form = panel.forms["options"]
    panel.set_input_path("source", examples_dir() / "question_bank.md")
    assert panel.missing_inputs(panel.collect_inputs()) == []
    form.set_field("retrieval", True)
    panel.start_run()
    assert "Fill in: Taught log (.csv)" in panel.strip.text()
    panel.set_input_path("taught_log", examples_dir() / "taught_log.csv")
    form.set_field("today", "2026-10-08")
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.strip.text()
