"""Phase 7: shortcuts, settings fields, app icon, usage recording."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QShortcut
from pytestqt.qtbot import QtBot

from staffroom.core import usage
from staffroom.core.config import load_config
from staffroom.shell.main_window import MainWindow
from staffroom.shell.sidebar import LIBRARY
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
    assert window.sidebar.current() == LIBRARY
    assert window.stack.currentWidget() is window.library_page


def _shortcuts(window: MainWindow) -> dict[str, QShortcut]:
    return {s.key().toString(): s for s in window.findChildren(QShortcut)}


def test_cmd_numbers_follow_the_sidebar_top_to_bottom(window: MainWindow) -> None:
    """⌘1-⌘9 are the nine tools in the order the grouped sidebar lists them
    (the Library is ⌘K): Classroom, Worksheet, Quiz, Parsons, Trace, Bugs,
    Fade, Pseudocode, Marks."""
    order = window.sidebar.tool_names()
    assert order == [
        "classroom",
        "worksheet",
        "quiz",
        "parsons",
        "trace",
        "bugs",
        "fade",
        "pseudocode",
        "marks",
    ]
    shortcuts = _shortcuts(window)
    for n, name in enumerate(order[:9], 1):
        shortcuts[f"Ctrl+{n}"].activated.emit()
        panel = window.stack.currentWidget()
        assert isinstance(panel, ToolPanel) and panel.plugin.name == name
        assert window.sidebar.current() == name
        item = window.sidebar.item(name)
        assert item is not None and f"(⌘{n})" in item.toolTip()


def test_cmd_shift_l_switches_the_theme(window: MainWindow) -> None:
    theme = window.config.general.theme
    _shortcuts(window)["Ctrl+Shift+L"].activated.emit()
    assert window.config.general.theme != theme


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
    window.go_to_tool("hello")
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel)
    panel.set_input_path("source", example_marks)
    with qtbot.waitSignal(panel.run_finished, timeout=10000):
        panel.start_run()
    rows = usage.summary()
    assert [(u.name, u.runs) for u in rows] == [("hello", 1)]
