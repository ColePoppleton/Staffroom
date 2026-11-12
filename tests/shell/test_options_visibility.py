"""Tool options forms show only the fields that apply, with readable
choices (#91), in the real tool panels."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets.choice import ChoiceWidget
from staffroom.tools.worksheet.lessons import LESSONS


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


def test_gates_and_laws_show_only_for_the_lessons_that_read_them(window: MainWindow) -> None:
    panel = _panel(window, "worksheet")
    lesson = panel.grouped["lesson"]
    for key, les in LESSONS.items():
        lesson.set_value(key)
        assert lesson.value() == key
        assert panel.groups["level"].isVisibleTo(panel) == ("level" in les.uses), key
        assert panel.groups["laws"].isVisibleTo(panel) == ("laws" in les.uses), key


def test_worksheet_choices_read_as_words(window: MainWindow) -> None:
    form = _panel(window, "worksheet").forms["options"]
    assert "topic" not in form.widgets  # the lesson is chosen above the form (#75)
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


def test_quiz_folds_spec_points_and_title_under_more(window: MainWindow) -> None:
    """#17: the format and the source of questions are switches of their own;
    the form keeps the count and seed on one row, the rest under More."""
    form = _panel(window, "quiz").forms["options"]
    assert form.shown_fields() == ["count", "seed"]
    form.set_more_open(True)
    assert form.shown_fields() == ["count", "seed", "spec", "title"]


def test_parsons_granularity_is_a_switch(window: MainWindow) -> None:
    form = _panel(window, "parsons").forms["options"]
    split = form.widgets["granularity"]
    assert isinstance(split, ChoiceWidget)
    split.buttons["line"].click()
    assert form.value().granularity == "line"
