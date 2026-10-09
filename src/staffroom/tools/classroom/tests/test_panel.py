"""The classroom panel names its own destination: the sessions folder."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from staffroom.core.config import Config
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
