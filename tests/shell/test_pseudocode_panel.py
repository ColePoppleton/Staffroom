from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
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


def test_translate_and_copy(window: MainWindow, qtbot: QtBot) -> None:
    window.sidebar.select("pseudocode")
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel)
    panel.set_text("pasted", "total = 0\nfor i in range(3):\n    total += i\nprint(total)\n")
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.run_bar.status.text()
    out = panel.results.text_views["output"].toPlainText()
    assert "for i = 0 to 2" in out and "next i" in out
    assert "Everything translated" in panel.results.text_views["report"].toPlainText()
    # The translation is the main view; its Copy button sits in the tab bar's
    # corner while its tab is showing. The notes sit below it.
    assert panel.results.main_keys == ["output"]
    assert "report" in panel.results.sections
    copy = panel.results.copy_buttons["output"]
    assert copy.text() == "Copy" and copy.isVisible()
    copy.click()
    assert QApplication.clipboard().text() == out
