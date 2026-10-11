"""Docs screenshots show a teacher's folders, never the machine that made
them (#14): the Settings fields, the run bar and the result line read
``~/…``, and an image that would still show a temp or checkout path is
refused instead of saved."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.shell import screenshot_paths
from staffroom.shell.app import _save_screenshot, build_window, parse_args


@pytest.fixture
def exits(qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Record app.exit() instead of quitting the test's event loop."""
    calls: list[int] = []
    monkeypatch.setattr(qapp, "exit", calls.append)
    return calls


def _configure(tmp_path: Path) -> None:
    resources = tmp_path / "worktrees" / "feat" / "scripts" / "screenshots" / "resources"
    resources.mkdir(parents=True)
    config = load_config()
    config.general.resources_root = str(resources)
    config.general.sessions_root = str(tmp_path / "sessions")
    config.save()


def test_settings_screenshot_shows_home_relative_folders(
    qtbot: QtBot, qapp: QApplication, tmp_path: Path, exits: list[int]
) -> None:
    _configure(tmp_path)
    shot = tmp_path / "docs" / "settings.png"
    window = build_window(parse_args(["--settings", "--screenshot", str(shot)]))
    qtbot.addWidget(window)
    window.show()
    settings = window.settings
    assert str(tmp_path) in settings.resources_root.edit.text()  # the real path, before

    _save_screenshot(qapp, window, shot)

    assert exits == [0] and shot.exists()
    assert settings.resources_root.edit.text() == "~/Documents/Teaching resources"
    assert settings.sessions_root.edit.text() == "~/TeachingSessions"
    assert settings.output_dir.edit.text() == ""  # the default: next to the input
    assert "~/.config/staffroom/library.db" in settings.library_statement.text()
    assert screenshot_paths.leaks(window) == []
    # Only the pixels changed: nothing was saved over the real settings.
    assert load_config().general.resources_root.endswith("resources")
    assert load_config().general.resources_root != "~/Documents/Teaching resources"


def test_tool_screenshot_shows_where_a_fresh_install_would_write(
    qtbot: QtBot, qapp: QApplication, tmp_path: Path, exits: list[int], example_marks: Path
) -> None:
    """Next to the input (here the repository's examples folder), not the
    screenshot's throwaway folder; a tool with no input file shows
    ``~/TeachingSessions/outputs/<tool>``."""
    _configure(tmp_path)
    shot = tmp_path / "marks.png"
    args = parse_args(["--tool", "marks", "--open", str(example_marks), "--screenshot", str(shot)])
    window = build_window(args)
    qtbot.addWidget(window)
    window.show()
    _save_screenshot(qapp, window, shot)
    assert exits == [0] and shot.exists()
    assert window.panel_for("marks").run_bar.folder.text() == "Writes to ~/Staffroom/examples"

    exits.clear()
    window = build_window(parse_args(["--tool", "worksheet", "--screenshot", str(shot)]))
    qtbot.addWidget(window)
    window.show()
    _save_screenshot(qapp, window, shot)
    assert exits == [0]
    bar = window.panel_for("worksheet").run_bar
    assert bar.folder.text() == "Writes to ~/TeachingSessions/outputs/worksheet"


@pytest.mark.parametrize(
    "text",
    [
        "/Users/someone/Documents/x.py",
        "/var/folders/qb/abc/T/staffroom-shots.X/sessions",
        "~/Teaching-Tools-worktrees/feat/89-sidebar-identity/scripts",
    ],
)
def test_a_screenshot_that_would_show_a_machine_path_is_refused(
    qtbot: QtBot,
    qapp: QApplication,
    tmp_path: Path,
    exits: list[int],
    text: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    shot = tmp_path / "docs" / "settings.png"
    window = build_window(parse_args(["--settings", "--screenshot", str(shot)]))
    qtbot.addWidget(window)
    window.show()
    stray = QLabel("", window.settings)
    stray.show()
    # Set after neutralising would run, as a path the aliases do not know.
    original = screenshot_paths.neutralise

    def neutralise_then_leak(win: object, table: screenshot_paths.Aliases, blank: str) -> None:
        original(win, table, blank)  # type: ignore[arg-type]
        stray.setText(text)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(screenshot_paths, "neutralise", neutralise_then_leak)
        _save_screenshot(qapp, window, shot)
    assert exits == [1]
    assert not shot.exists()
    assert "REFUSED" in capsys.readouterr().out


def test_neutral_replaces_the_longest_prefix_first() -> None:
    table = [("/a/b/c", "~/Documents/Teaching resources"), ("/a/b", "~")]
    assert screenshot_paths.neutral("/a/b/c/Year 9/x.py and /a/b/y", table) == (
        "~/Documents/Teaching resources/Year 9/x.py and ~/y"
    )
