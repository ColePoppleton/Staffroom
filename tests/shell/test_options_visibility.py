"""Tool options forms show only the fields that apply, with readable
choices (#91), in the real tool panels."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QComboBox
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets.choice import ChoiceWidget
from staffroom.tools.worksheet.logic import GENERATORS


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    return win


def _panel(window: MainWindow, tool: str) -> ToolPanel:
    window.go_to_tool(tool)
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == tool
    return panel


def test_boolean_laws_show_only_for_simplification(window: MainWindow) -> None:
    form = _panel(window, "worksheet").forms["options"]
    for topic in GENERATORS:
        form.set_field("topic", topic)
        shown = form.shown_fields()
        assert ("laws" in shown) == (topic == "boolean_simplification"), topic
        assert ("level" in shown) == (topic == "truth_tables"), topic


def test_worksheet_choices_read_as_words(window: MainWindow) -> None:
    form = _panel(window, "worksheet").forms["options"]
    topic = form.widgets["topic"]
    assert isinstance(topic, QComboBox)
    assert topic.currentText() == "Binary, denary and hexadecimal"
    difficulty = form.widgets["difficulty"]
    assert isinstance(difficulty, ChoiceWidget)
    assert [b.text() for b in difficulty.buttons.values()] == ["Easy", "Medium", "Hard"]
    formats = form.widgets["formats"]
    assert isinstance(formats, ChoiceWidget)
    assert [b.text() for b in formats.buttons.values()] == ["Word + PDF", "Word", "PDF"]


def test_fade_ranges_show_only_for_the_listed_order(window: MainWindow, qtbot: QtBot) -> None:
    panel = _panel(window, "fade")
    form = panel.forms["options"]
    assert "ranges" not in form.shown_fields()
    form.set_field("order", "ranges")
    form.set_field("ranges", "1-2")
    assert "ranges" in form.shown_fields()
    # Switch back: the ranges hide and keep what was typed, and the run does not
    # trip over lines the teacher can no longer see.
    form.set_field("order", "top_down")
    assert "ranges" not in form.shown_fields()
    assert form.held().ranges == "1-2" and form.value().ranges == ""
    panel.set_text("source", "x = 1\ny = 2\nprint(x + y)\n")
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.strip.text()


def test_quiz_hides_what_its_format_and_mode_do_not_use(window: MainWindow) -> None:
    form = _panel(window, "quiz").forms["options"]
    assert {"title", "today"}.isdisjoint(form.shown_fields())  # Kahoot, no retrieval
    form.set_field("fmt", "donow")
    assert "title" in form.shown_fields()
    form.set_field("retrieval", True)
    assert "today" in form.shown_fields()


def test_parsons_granularity_is_a_switch(window: MainWindow) -> None:
    form = _panel(window, "parsons").forms["options"]
    split = form.widgets["granularity"]
    assert isinstance(split, ChoiceWidget)
    split.buttons["line"].click()
    assert form.value().granularity == "line"
