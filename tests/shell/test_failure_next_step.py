"""After a failed run the output pane says what to do (or nothing), never
"Press Run"; a failure that names an input marks it; an Inputs box says how
many input() calls the program has (#21)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel

ASKS_TWICE = 'w = int(input("Width? "))\nh = int(input("Height? "))\nprint(w * h)\n'


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


def _run(panel: ToolPanel, qtbot: QtBot) -> bool:
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as blocker:
        panel.start_run()
    return bool(blocker.args[0])


def _pane_texts(panel: ToolPanel) -> set[str]:
    return {label.text() for label in panel.results.empty_labels}


def test_missing_input_shows_the_next_step_and_marks_the_inputs_box(
    window: MainWindow, qtbot: QtBot
) -> None:
    panel = _panel(window, "trace")
    assert all(t.startswith("Press Trace") for t in _pane_texts(panel))
    panel.set_text("source", ASKS_TWICE)
    panel.set_text("stdin", "4")
    assert not _run(panel, qtbot)
    assert panel.strip.text() == "The pasted code asked for a 2nd input, but was given only 1 line."
    next_step = (
        "The pasted code calls input() twice. "
        "Type 2 lines in the Inputs box, then press Trace again."
    )
    assert _pane_texts(panel) == {next_step}
    assert all(label.property("role") == "next-step" for label in panel.results.empty_labels)
    group = panel.groups["stdin"]
    assert group.flagged and panel.text_areas["stdin"].property("flagged") is True
    assert group.help_label.text() == "Needs 2 lines, one per input() call."
    assert group.help_label.property("role") == "flag"
    # Typing in the box is fixing it: the mark and the hint go, the help comes back.
    panel.text_areas["stdin"].appendPlainText("5")
    assert not group.flagged and panel.text_areas["stdin"].property("flagged") is False
    assert group.help_label.text() == "What the program reads from input(), one line each."
    assert _run(panel, qtbot)
    assert panel.strip.text().startswith("3 rows")


def test_a_new_run_clears_the_mark_and_the_next_step(window: MainWindow, qtbot: QtBot) -> None:
    panel = _panel(window, "trace")
    panel.set_text("source", ASKS_TWICE)
    assert not _run(panel, qtbot)
    assert panel.groups["stdin"].flagged
    panel.set_text("source", "x = 1\nprint(x)\n")
    assert _run(panel, qtbot)
    assert not panel.groups["stdin"].flagged
    assert all(t.startswith("Press Trace") for t in _pane_texts(panel))


def test_a_failure_with_no_next_step_leaves_the_pane_empty(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("Lesson 3: while loops\n")
    panel = _panel(window, "hello")
    panel.set_input_path("source", notes)
    assert not _run(panel, qtbot)
    assert _pane_texts(panel) <= {""}
    assert not any(group.flagged for group in panel.groups.values())


@pytest.mark.parametrize("tool", ["trace", "bugs"])
def test_the_inputs_box_counts_the_input_calls(window: MainWindow, tool: str) -> None:
    panel = _panel(window, tool)
    area = panel.text_areas["stdin"]
    assert area.placeholderText() == "One line per input() call"
    panel.set_text("source", ASKS_TWICE)
    assert area.placeholderText() == "2 input() calls:\none line each"
    panel.set_text("source", "while True:\n    if input() == 'q':\n        break\n")
    assert area.placeholderText() == "At least 1 input() call\n(in a loop): one line each"
    panel.set_text("source", "print('hi')\n")
    assert area.placeholderText() == "No input() calls in this program:\nleave this empty"
    panel.set_text("source", "")
    assert area.placeholderText() == "One line per input() call"
