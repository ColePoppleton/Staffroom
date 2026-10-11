"""The classroom panel through the launcher: resource picker, label field,
sessions ActionTable with Diff / Promote / Re-open, diff TextView."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core import launch
from staffroom.core.config import load_config
from staffroom.core.library.service import LibraryService
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []
    monkeypatch.setattr(launch, "_popen", lambda argv: calls.append(list(argv)))
    return calls


@pytest.fixture
def window(
    qtbot: QtBot, service: LibraryService, resources_root: Path, tmp_path: Path
) -> MainWindow:
    config = load_config()
    config.general.resources_root = str(resources_root)
    config.general.sessions_root = str(tmp_path / "sessions")
    win = MainWindow(config, library=service, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    win.sidebar.select("classroom")
    return win


def panel_of(window: MainWindow) -> ToolPanel:
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == "classroom"
    return panel


def test_panel_renders_new_widgets(window: MainWindow) -> None:
    panel = panel_of(window)
    assert "resource" in panel.resource_pickers and "label" in panel.text_fields
    table = panel.results.action_tables["sessions"]
    assert set(table.buttons) == {"diff", "reopen", "promote"}
    assert not table.buttons["diff"].isEnabled()  # nothing selected
    assert table.empty.isVisibleTo(panel)  # refreshed on show: no sessions yet
    assert "diff" in panel.results.text_views


def test_missing_inputs_block_run(window: MainWindow) -> None:
    panel = panel_of(window)
    panel.start_run()
    assert panel.worker is None
    assert "Resource" in panel.strip.text() and "Lesson label" in panel.strip.text()


def test_open_diff_promote_reopen(
    window: MainWindow, qtbot: QtBot, resources_root: Path, tmp_path: Path, runs: list[list[str]]
) -> None:
    panel = panel_of(window)
    original = resources_root / "Python" / "Python_Course" / "while_loops.py"
    before = original.read_bytes()
    panel.set_input_path("resource", original)
    panel.set_text("label", "P3 Y9 loops")
    with qtbot.waitSignal(panel.run_finished, timeout=5000) as blocker:
        panel.start_run()
    assert blocker.args == [True]
    copy = tmp_path / "sessions"
    copies = list(copy.rglob("while_loops.py"))
    assert len(copies) == 1 and copies[0].parent.name == "P3 Y9 loops"
    assert runs[-1] == ["open", "-a", "Thonny", str(copies[0])]
    assert panel.run_bar._folder == copies[0].parent  # the run bar named the right place
    table = panel.results.action_tables["sessions"]
    assert table.model.rowCount() == 1

    copies[0].write_text(copies[0].read_text() + "print('edited in class')\n")
    assert original.read_bytes() == before

    table.select_first()
    assert table.buttons["diff"].isEnabled()
    with qtbot.waitSignal(panel.run_finished, timeout=5000):
        table.buttons["diff"].click()
    assert "+print('edited in class')" in panel.results.text_views["diff"].toPlainText()

    table.select_first()
    with qtbot.waitSignal(panel.run_finished, timeout=5000):
        table.buttons["promote"].click()
    assert (
        (original.parent / "while_loops_v2.py").read_text().endswith("print('edited in class')\n")
    )
    assert original.read_bytes() == before
    assert "while_loops_v2.py" in panel.strip.text()
    # Promote writes next to the original; the run bar still describes Open for class.
    assert panel.run_bar._folder == copies[0].parent

    table.select_first()
    with qtbot.waitSignal(panel.run_finished, timeout=5000):
        table.buttons["reopen"].click()
    assert runs[-1][-1] == str(copies[0])


def test_settings_show_local_sessions_default(window: MainWindow, tmp_path: Path) -> None:
    window.sidebar.settings_button.click()
    # Tests set STAFFROOM_SESSIONS (#37), so Settings names that folder.
    placeholder = window.settings.sessions_root.edit.placeholderText()
    assert placeholder == f"{tmp_path / 'sessions'}  (default, local)"
    assert window.settings.editor_preset.currentText() == "Thonny"
    window.settings.editor_preset.setCurrentText("IDLE")
    assert window.config.general.editor_command == "python3 -m idlelib {file}"
    assert load_config().general.editor_command == "python3 -m idlelib {file}"
