"""The classroom panel names its own destination: the sessions folder."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from staffroom.core import launch
from staffroom.core.config import Config
from staffroom.core.plugin import RunContext
from staffroom.tools.classroom import plugin
from staffroom.tools.classroom.panel import copies_to, panel_spec

DAY = date(2026, 10, 9)


def config_with_sessions(root: Path) -> Config:
    config = Config(path=root / "config.toml")
    config.general.sessions_root = str(root / "sessions")
    return config


def test_copies_to_is_the_session_folder_for_the_label(tmp_path: Path) -> None:
    config = config_with_sessions(tmp_path)
    folder = copies_to({"label": "P3 Y9 loops"}, config, today=DAY)
    assert folder == tmp_path / "sessions" / "2026-10-09" / "P3 Y9 loops"
    assert not folder.exists()  # naming the folder never creates it


def test_copies_to_uses_the_same_safe_folder_name_as_the_copy(tmp_path: Path) -> None:
    config = config_with_sessions(tmp_path)
    folder = copies_to({"label": "  P3/Y9: loops?  "}, config, today=DAY)
    assert folder == tmp_path / "sessions" / "2026-10-09" / "P3Y9 loops"


def test_copies_to_falls_back_to_today_without_a_label(tmp_path: Path) -> None:
    config = config_with_sessions(tmp_path)
    assert copies_to({}, config, today=DAY) == tmp_path / "sessions" / "2026-10-09"
    assert copies_to({"label": "   "}, config, today=DAY) == tmp_path / "sessions" / "2026-10-09"


def test_panel_declares_where_it_copies() -> None:
    writes_to = panel_spec().writes_to
    assert writes_to is not None
    assert writes_to.verb == "Copies to" and writes_to.open_label == "Open sessions folder"
    assert writes_to.folder is copies_to


def test_copies_to_is_today_unless_a_screenshot_pins_the_day(tmp_path: Path) -> None:
    """A teacher's launcher never sets ``screenshot_day``: the run bar shows
    today. Only ``staffroom --screenshot --today`` pins the day it shows."""
    config = config_with_sessions(tmp_path)
    assert config.screenshot_day is None
    assert copies_to({}, config) == tmp_path / "sessions" / date.today().isoformat()
    config.screenshot_day = DAY
    assert copies_to({"label": "P3 Y9 loops"}, config) == (
        tmp_path / "sessions" / "2026-10-09" / "P3 Y9 loops"
    )


def test_a_pinned_screenshot_day_never_moves_where_a_copy_goes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pinned day is display-only: Open for class still copies into
    today's session folder, so a lesson copy can never land under another day."""
    monkeypatch.setattr(launch, "_popen", lambda _argv: None)  # no editor
    resource = tmp_path / "average.py"
    resource.write_text("print(1)  # FAKE DATA\n", encoding="utf-8")
    config = config_with_sessions(tmp_path)
    config.screenshot_day = date(2001, 1, 1)
    ctx = RunContext(config=config, output_dir=tmp_path / "out")
    result = plugin.run({"resource": resource, "label": "P3 Y9 loops"}, ctx)
    today = tmp_path / "sessions" / date.today().isoformat() / "P3 Y9 loops"
    assert result.files == [today / "average.py"]
    assert (today / "average.py").is_file()
    assert not (tmp_path / "sessions" / "2001-01-01").exists()
