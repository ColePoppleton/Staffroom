"""Input mistakes in the launcher are teacher messages, not tracebacks (#14):
picking the wrong kind of file shows one red line in the run bar and the log,
with no Python exception names or stack frames."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel

TRACEBACK_WORDS = ("Traceback", "ValueError", "UnicodeDecodeError", "KeyError", 'File "')


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
    # go_to_tool opens hidden tools (hello) too; the sidebar only lists visible ones.
    window.go_to_tool(tool)
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == tool
    return panel


def _run_fails(panel: ToolPanel, qtbot: QtBot) -> str:
    with qtbot.waitSignal(panel.run_finished, timeout=10000) as blocker:
        panel.start_run()
    assert blocker.args == [False]
    assert panel.results.log_view is not None
    log_text = panel.results.log_view.toPlainText()
    for word in TRACEBACK_WORDS:
        assert word not in log_text, log_text
        assert word not in panel.run_bar.status.text()
    return log_text


@pytest.mark.parametrize(("tool", "key"), [("marks", "marks"), ("hello", "source")])
def test_wrong_file_type_is_one_line(
    window: MainWindow, qtbot: QtBot, tmp_path: Path, tool: str, key: str
) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("Lesson 3: while loops\n")
    panel = _panel(window, tool)
    panel.set_input_path(key, notes)
    log_text = _run_fails(panel, qtbot)
    status = panel.run_bar.status.text()
    assert "notes.txt" in status and ".csv" in status and ".xlsx" in status
    assert "\n" not in status
    assert status in log_text


def test_fade_bad_ranges_is_one_line(window: MainWindow, qtbot: QtBot) -> None:
    panel = _panel(window, "fade")
    panel.set_text("pasted", "x = 1\ny = 2\nprint(x + y)\n")
    form = panel.forms["options"]
    widgets = {
        name: form.layout().itemAt(i * 2 + 1).widget()
        for i, name in enumerate(form.schema.__dataclass_fields__)
    }
    widgets["order"].setCurrentText("ranges")
    widgets["ranges"].setText("abc")
    assert form.value().order == "ranges" and form.value().ranges == "abc"
    _run_fails(panel, qtbot)
    status = panel.run_bar.status.text()
    assert "Line ranges like 3-5, 8" in status and "'abc'" in status
