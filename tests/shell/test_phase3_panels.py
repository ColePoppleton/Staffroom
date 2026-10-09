"""parsons and worksheet through the launcher: pasted code via TextArea,
preview TextView filled after a run, files written."""

from __future__ import annotations

from pathlib import Path

import pytest
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


def test_parsons_from_pasted_code(window: MainWindow, qtbot: QtBot, tmp_path: Path) -> None:
    window.sidebar.select("parsons")
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and "source" in panel.code_sources
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as first:
        panel.start_run()  # nothing chosen or pasted: a user-facing error, not a crash
    assert first.args == [False] and "paste some code" in panel.strip.text()
    panel.set_text("source", "x = 1\nif x > 0:\n    print(x)\n")
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as blocker:
        panel.start_run()
    assert blocker.args == [True]
    assert "Correct order:" in panel.results.text_views["preview"].toPlainText()
    assert any(p.suffix == ".pdf" for p in (tmp_path / "out").iterdir())


def test_worksheet_panel_runs(window: MainWindow, qtbot: QtBot, tmp_path: Path) -> None:
    window.sidebar.select("worksheet")
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel)
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as blocker:
        panel.start_run()
    assert blocker.args == [True]
    preview = panel.results.text_views["preview"].toPlainText()
    assert "Worksheet: Binary" in preview and "seed 42" in preview
    assert (tmp_path / "out" / "binary_medium_s42_key.docx").exists()
