"""The output folder is predictable and shown before Run; screenshot runs
leave nothing behind."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.shell.app import build_window, parse_args
from staffroom.shell.main_window import MainWindow
from staffroom.shell.widgets.run_bar import abbreviate_path


def test_run_bar_shows_the_folder_before_the_run(qtbot: QtBot, tmp_path: Path) -> None:
    config = load_config()
    config.general.sessions_root = str(tmp_path / "sessions")
    config.general.resources_root = str(tmp_path / "resources")
    window = MainWindow(config, auto_index=False)
    qtbot.addWidget(window)
    window.show()
    panel = window.panel_for("worksheet")
    expected = tmp_path / "sessions" / "outputs" / "worksheet"
    assert panel.run_bar._folder == expected
    assert panel.run_bar.folder.isVisibleTo(panel)
    assert panel.run_bar.folder.text().startswith("Writes to ")
    assert panel.run_bar.folder.toolTip() == str(expected)
    # Before the first run the strip offers the same folder as a chip.
    assert panel.strip.folder_chip.isVisibleTo(panel)
    assert panel.strip.folder_chip.toolTip() == str(expected)
    # While running the chip stays, so the folder can be opened at any time.
    panel.strip.set_running()
    assert panel.strip.folder_chip.isVisibleTo(panel)


def test_run_bar_follows_the_chosen_input(
    qtbot: QtBot, tmp_path: Path, example_marks: Path
) -> None:
    config = load_config()
    config.general.resources_root = str(tmp_path / "resources")
    window = MainWindow(config, auto_index=False)
    qtbot.addWidget(window)
    window.show()
    panel = window.panel_for("hello")
    assert panel.run_bar._folder is not None
    assert panel.run_bar._folder.name == "hello"
    panel.set_input_path("source", example_marks)
    assert panel.run_bar._folder == example_marks.parent


def test_screenshot_mode_writes_to_a_throwaway_folder(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example_marks: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    args = parse_args(
        ["--tool", "hello", "--open", str(example_marks), "--screenshot", str(tmp_path / "s.png")]
    )
    window = build_window(args)
    qtbot.addWidget(window)
    panel = window.panel_for("hello")
    out = panel.output_dir(panel.collect_inputs())
    assert out.name.startswith("staffroom-screenshot-")
    assert out.is_dir()
    assert out != example_marks.parent and out != Path.cwd()
    assert window.config.read_only


def test_screenshot_today_pins_the_day_the_classroom_run_bar_shows(
    qtbot: QtBot, tmp_path: Path
) -> None:
    """``--today`` makes the docs shot of Classroom the same bytes on any day
    (#116). It only changes what the run bar says; see classroom's tests for
    the copy itself, which always goes into today's folder."""
    args = parse_args(
        ["--tool", "classroom", "--today", "2026-10-09", "--screenshot", str(tmp_path / "s.png")]
    )
    window = build_window(args)
    qtbot.addWidget(window)
    assert window.config.screenshot_day == date(2026, 10, 9)
    bar = window.panel_for("classroom").run_bar
    assert bar._folder is not None and bar._folder.name == "2026-10-09"
    assert bar.folder.text().endswith("2026-10-09")


def test_today_is_refused_outside_screenshot_mode(capsys: pytest.CaptureFixture[str]) -> None:
    """The launcher a teacher opens never takes a pinned day."""
    with pytest.raises(SystemExit):
        parse_args(["--tool", "classroom", "--today", "2026-10-09"])
    assert "--today only works with --screenshot" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        parse_args(["--today", "9/10/2026", "--screenshot", "s.png"])
    assert parse_args([]).today is None


def test_abbreviate_path() -> None:
    assert abbreviate_path(Path.home() / "TeachingSessions") == "~/TeachingSessions"
    long = Path("/Volumes/" + "a" * 60 + "/outputs/worksheet")
    short = abbreviate_path(long)
    assert len(short) <= 44 and "…" in short and short.endswith("outputs/worksheet")


def test_classroom_run_bar_names_the_sessions_folder(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_config()
    config.general.sessions_root = str(tmp_path / "sessions")
    config.general.resources_root = str(tmp_path / "resources")
    window = MainWindow(config, auto_index=False)
    qtbot.addWidget(window)
    window.show()
    panel = window.panel_for("classroom")
    today = tmp_path / "sessions" / date.today().isoformat()
    bar = panel.run_bar
    assert bar._folder == today
    assert bar.folder.text().startswith("Copies to ")
    assert panel.strip.folder_chip.text() == "Open sessions folder"
    # Typing the label moves the folder to where the copy will actually go.
    panel.set_text("label", "P3 Y9 loops")
    assert bar._folder == today / "P3 Y9 loops"
    assert bar.folder.toolTip() == str(today / "P3 Y9 loops")
    assert bar.folder.text().endswith("P3 Y9 loops")
    assert not (tmp_path / "sessions").exists()  # nothing created until asked
    assert panel.strip.folder_chip.toolTip() == str(today / "P3 Y9 loops")
    opened: list[Path] = []
    monkeypatch.setattr(window.library, "open_externally", opened.append)
    panel.strip.folder_chip.click()
    assert (today / "P3 Y9 loops").is_dir()  # created on demand, then opened
    assert opened == [today / "P3 Y9 loops"]


def test_every_other_tool_still_names_the_output_folder(qtbot: QtBot, tmp_path: Path) -> None:
    config = load_config()
    config.general.sessions_root = str(tmp_path / "sessions")
    config.general.resources_root = str(tmp_path / "resources")
    window = MainWindow(config, auto_index=False)
    qtbot.addWidget(window)
    others = [p.name for p in window.plugins if p.name != "classroom"]
    assert others
    for name in others:
        panel = window.panel_for(name)
        assert panel.spec.writes_to is None, name
        bar = panel.run_bar
        assert bar._folder == panel.output_dir(panel.collect_inputs()), name
        assert bar.folder.text().startswith("Writes to "), name
        assert panel.strip.folder_chip.text() == "Open output folder", name
