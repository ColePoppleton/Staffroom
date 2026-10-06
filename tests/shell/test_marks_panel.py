"""The marks panel: boundaries grid with presets, run, chart image shown,
per-script table shown but not saved."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from teaching_tools.core.config import load_config
from teaching_tools.shell.main_window import MainWindow
from teaching_tools.shell.tool_panel import ToolPanel


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    win.sidebar.select("marks")
    return win


def test_presets_apply_and_save(window: MainWindow, qtbot: QtBot) -> None:
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == "marks"
    grid = panel.grids["boundaries"]
    assert grid.model.rowCount() == 10  # OCR default
    grid.preset_combo.setCurrentText("A-level (A*-E)")
    grid.apply_button.click()
    assert grid.model.rowCount() == 7 and grid.value().rows[0][0] == "A*"
    grid.model.setData(grid.model.index(0, 1), "85")
    grid.add_preset("Custom A", grid.value().rows)
    grid.preset_saved.emit("Custom A", grid.value())
    assert "Custom A" in load_config().tool("marks")["presets"]
    assert "Saved preset" in panel.run_bar.status.text()


def test_run_shows_chart_and_tables(
    window: MainWindow, qtbot: QtBot, example_marks_max: Path, tmp_path: Path
) -> None:
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel)
    panel.set_input_path("marks", example_marks_max)
    assert panel.previews["preview"].model.rowCount() == 11  # MAX row previewed too
    with qtbot.waitSignal(panel.run_finished, timeout=10000) as blocker:
        panel.start_run()
    assert blocker.args == [True]
    assert panel.results.tables["distribution"][0].rowCount() == 10
    assert panel.results.tables["grades"][0].rowCount() == 10
    assert panel.results.tables["worst"][0].rowCount() == 5
    image = panel.results.images["chart"]
    assert image.pixmap() is not None and not image.pixmap().isNull()
    saved = sorted(p.name for p in (tmp_path / "out").iterdir())
    assert saved == [
        "marks_10x_max_distribution.csv",
        "marks_10x_max_distribution.png",
        "marks_10x_max_questions.csv",
    ]
