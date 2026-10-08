"""Phase 7: shortcuts, settings fields, app icon, usage recording."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core import usage
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


def test_cmd_k_focuses_library_search(window: MainWindow) -> None:
    window.focus_library_search()
    assert window.sidebar.mode() == "resources"
    assert window.stack.currentWidget() is window.library_page


def test_cmd_number_jumps_to_tool(window: MainWindow) -> None:
    second = window.plugins[1].name
    window.go_to_tool(second)
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == second
    assert window.sidebar.mode() == "tools"


def test_settings_board_and_house_style_persist(window: MainWindow) -> None:
    s = window.settings
    s.board.setCurrentIndex(s.board.findData("aqa"))
    s.house_header.setText("Example High")
    s.house_footer.setText("Computing")
    s._on_house()
    cfg = load_config()
    assert cfg.general.board == "aqa"
    assert cfg.general.house_header == "Example High" and cfg.general.house_footer == "Computing"


def test_app_icon_assets_exist() -> None:
    assets = Path(__file__).resolve().parents[2] / "src" / "staffroom" / "shell" / "assets"
    assert (assets / "icon.png").stat().st_size > 1000
    assert (assets / "icon.icns").stat().st_size > 1000


def test_run_records_usage(window: MainWindow, qtbot: QtBot, example_marks: Path) -> None:
    window.sidebar.select("hello")
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel)
    panel.set_input_path("source", example_marks)
    with qtbot.waitSignal(panel.run_finished, timeout=10000):
        panel.start_run()
    rows = usage.summary()
    assert [(u.name, u.runs) for u in rows] == [("hello", 1)]
