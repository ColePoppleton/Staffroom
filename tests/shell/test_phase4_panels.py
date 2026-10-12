"""trace, bugs and fade through the launcher."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel

PROGRAM = "total = 0\nfor i in range(3):\n    total = total + i\nprint(total)\n"


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    return win


def run_tool(window: MainWindow, qtbot: QtBot, name: str) -> ToolPanel:
    window.sidebar.select(name)
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == name
    panel.set_text("source", PROGRAM)
    with qtbot.waitSignal(panel.run_finished, timeout=60000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.strip.text()
    return panel


def test_trace_panel(window: MainWindow, qtbot: QtBot, tmp_path: Path) -> None:
    panel = run_tool(window, qtbot, "trace")
    model = panel.results.tables["table"][0]
    assert model.columnCount() >= 4 and model.rowCount() >= 8
    pages = panel.results.page_previews["pages"]
    assert pages.path("key") == tmp_path / "out" / "pasted_code_trace_key.pdf"
    assert pages.page_count("sheet") >= 1


def test_bugs_panel(window: MainWindow, qtbot: QtBot, tmp_path: Path) -> None:
    panel = run_tool(window, qtbot, "bugs")
    assert panel.results.card_lists["key"].count() >= 1
    assert (tmp_path / "out" / "pasted_code_bug1.py").exists()
    assert panel.results.page_previews["pages"].path("sheet") == (
        tmp_path / "out" / "pasted_code_bugs.pdf"
    )


def test_fade_panel(window: MainWindow, qtbot: QtBot, tmp_path: Path) -> None:
    panel = run_tool(window, qtbot, "fade")
    pages = panel.results.page_previews["pages"]
    assert pages.path("sheet") == tmp_path / "out" / "pasted_code_faded.pdf"
    assert pages.page_count("key") >= 1
    assert (tmp_path / "out" / "pasted_code_faded_key.docx").exists()
