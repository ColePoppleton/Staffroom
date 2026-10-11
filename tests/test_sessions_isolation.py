"""No test reaches the teacher's real sessions folder (#37).

``isolated_home`` (root ``conftest.py``) sets ``STAFFROOM_SESSIONS`` for every
test and fails any test that resolves a sessions root under the real home.
These tests pin both halves: the default really is redirected, and the guard
really recognises an escape."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REAL_HOME, UNRECORDED_SESSIONS_ROOT, sessions_roots_under_real_home

from staffroom.core import paths
from staffroom.core.config import load_config


def test_the_default_sessions_root_is_this_tests_temp_folder(tmp_path: Path) -> None:
    root = paths.sessions_root("")
    assert root == tmp_path / "sessions"
    assert not root.resolve().is_relative_to(REAL_HOME)
    assert paths.fallback_output_dir("", "hello") == tmp_path / "sessions" / "outputs" / "hello"


def test_a_tool_with_nothing_configured_writes_under_the_temp_folder(tmp_path: Path) -> None:
    config = load_config()
    assert config.general.sessions_root == "" and config.general.output_dir == ""
    assert config.output_dir_for(None, "worksheet").is_relative_to(tmp_path)


def test_a_folder_chosen_in_settings_still_wins(tmp_path: Path) -> None:
    chosen = tmp_path / "chosen"
    assert paths.sessions_root(str(chosen)) == chosen


def test_without_the_override_the_default_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """What a teacher gets: neither variable set, so ~/TeachingSessions. Uses
    the unrecorded function (the recorded one would trip the guard, rightly);
    only a path is computed, nothing is created."""
    monkeypatch.delenv(paths.SESSIONS_ENV)
    assert UNRECORDED_SESSIONS_ROOT("") == Path.home() / "TeachingSessions"
    assert UNRECORDED_SESSIONS_ROOT("/Volumes/USB/Lessons") == Path("/Volumes/USB/Lessons")


def test_subprocesses_inherit_the_override(tmp_path: Path) -> None:
    """A test that runs ``staff`` in a subprocess gets the same isolation."""
    code = "from staffroom.core import paths; print(paths.sessions_root(''))"
    done = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=60, env=os.environ
    )
    assert done.returncode == 0, done.stderr
    assert Path(done.stdout.strip()) == tmp_path / "sessions"


def test_the_guard_recognises_a_root_under_the_real_home(tmp_path: Path) -> None:
    allowed = tmp_path.parent
    real_default = Path("~/TeachingSessions").expanduser()
    assert sessions_roots_under_real_home([real_default], allowed) == [real_default]
    assert sessions_roots_under_real_home([REAL_HOME / "Somewhere" / "else"], allowed)
    assert sessions_roots_under_real_home([tmp_path / "sessions"], allowed) == []
    # pytest's temp folder may itself sit inside the home (--basetemp): still allowed.
    inside = REAL_HOME / "pytest-basetemp"
    assert sessions_roots_under_real_home([inside / "t0" / "sessions"], inside) == []


REPO = Path(__file__).resolve().parents[1]


def test_the_screenshot_script_isolates_both_folders() -> None:
    script = (REPO / "scripts" / "screenshots.sh").read_text(encoding="utf-8")
    assert 'export STAFFROOM_HOME="$home"' in script
    assert 'export STAFFROOM_SESSIONS="$home/sessions"' in script


def test_the_contributing_guide_tries_things_out_in_throwaway_folders() -> None:
    """#18 and #37: fork first, a try-out that sets both variables, how long
    ``just check`` takes, and where to ask."""
    page = (REPO / "docs" / "contributing.md").read_text(encoding="utf-8")
    assert "Fork first" in page
    assert 'export STAFFROOM_HOME="$(mktemp -d)" STAFFROOM_SESSIONS="$(mktemp -d)"' in page
    assert "about three minutes" in page
    assert "## Where to ask" in page
