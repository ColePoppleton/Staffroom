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
    assert blocker.args == [True], panel.run_bar.status.text()
    assert panel.results.tables["chosen"][0].rowCount() == 10
    assert "Question - max 120 characters" in panel.results.text_views["preview"].toPlainText()
    assert (tmp_path / "out" / "question_bank_kahoot_s1.xlsx").exists()
