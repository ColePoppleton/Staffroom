import errno
import os
import stat
from pathlib import Path

import pytest

from staffroom.core import atomic, paths
from staffroom.core.config import NotSaved, load_config


def test_defaults_when_missing(isolated_home: Path) -> None:
    cfg = load_config()
    assert cfg.general.theme == "dark"
    assert cfg.path == isolated_home / "config.toml"
    assert not cfg.path.exists()


def test_save_and_reload(isolated_home: Path) -> None:
    cfg = load_config()
    cfg.general.theme = "light"
    cfg.tool("hello")["greeting"] = "hi"
    cfg.save()
    again = load_config()
    assert again.general.theme == "light"
    assert again.tool("hello") == {"greeting": "hi"}
    assert again.tool("unknown") == {}


def test_read_only_config_never_writes(isolated_home: Path) -> None:
    cfg = load_config()
    cfg.read_only = True
    cfg.general.theme = "light"
    cfg.save()
    assert not cfg.path.exists()


def test_unknown_general_keys_ignored(isolated_home: Path) -> None:
    paths.config_file().parent.mkdir(parents=True)
    paths.config_file().write_text('[general]\ntheme = "light"\nbogus = 1\n')
    assert load_config().general.theme == "light"


def test_default_output_dir(tmp_path: Path) -> None:
    assert paths.default_output_dir(tmp_path / "in.csv", "") == tmp_path
    assert paths.default_output_dir(None, str(tmp_path)) == tmp_path


def test_outputs_never_land_in_the_resources_folder(tmp_path: Path) -> None:
    root = tmp_path / "Resources"
    (root / "Python").mkdir(parents=True)
    inside = root / "Python" / "9a.py"
    inside.write_text("x = 1\n")
    out = paths.default_output_dir(inside, "", resources_root=str(root))
    assert out == paths.sessions_root("") / "outputs"
    assert not str(out).startswith(str(root))
    elsewhere = tmp_path / "other.py"
    assert paths.default_output_dir(elsewhere, "", resources_root=str(root)) == tmp_path
    assert (
        paths.default_output_dir(inside, str(tmp_path / "o"), resources_root=str(root))
        == tmp_path / "o"
    )


def test_default_output_dir_never_uses_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No configured folder and no input: a stable place under the sessions
    root, never wherever the process happens to be running from."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    sessions = tmp_path / "sessions"
    out = paths.default_output_dir(None, "", sessions_root=str(sessions), tool="worksheet")
    assert out == sessions / "outputs" / "worksheet"
    assert out != Path.cwd()
    # With everything left at its default the folder is under the default sessions root.
    assert paths.default_output_dir(None, "", tool="worksheet") == (
        paths.sessions_root("") / "outputs" / "worksheet"
    )
    assert paths.fallback_output_dir() == paths.sessions_root("") / "outputs"


def test_config_output_dir_for(isolated_home: Path, tmp_path: Path) -> None:
    cfg = load_config()
    cfg.general.sessions_root = str(tmp_path / "sessions")
    assert cfg.output_dir_for(None, "worksheet") == tmp_path / "sessions" / "outputs" / "worksheet"
    assert cfg.output_dir_for(tmp_path / "marks.csv", "marks") == tmp_path
    cfg.general.output_dir = str(tmp_path / "chosen")
    assert cfg.output_dir_for(None, "worksheet") == tmp_path / "chosen"
    assert cfg.output_dir_for(tmp_path / "marks.csv", "marks") == tmp_path / "chosen"


def test_outputs_from_the_resources_folder_follow_the_sessions_root(tmp_path: Path) -> None:
    root = tmp_path / "Resources"
    root.mkdir()
    inside = root / "9a.py"
    inside.write_text("x = 1\n")
    out = paths.default_output_dir(
        inside, "", resources_root=str(root), sessions_root=str(tmp_path / "s"), tool="trace"
    )
    assert out == tmp_path / "s" / "outputs" / "trace"


def test_library_exclude_round_trips() -> None:
    cfg = load_config()
    cfg.general.library_exclude = ["Pupil work", "Year 11/Mocks"]
    cfg.save()
    assert load_config().general.library_exclude == ["Pupil work", "Year 11/Mocks"]
    assert load_config().general.library_exclude is not cfg.general.library_exclude


# --- a failed write cannot truncate config.toml (#125) ---------------------------


def _no_space(fd: int) -> None:
    raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))


def test_a_failed_write_leaves_config_toml_unchanged(
    isolated_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = load_config()
    config.general.board = "aqa"
    assert config.save() is None
    before = config.path.read_bytes()

    monkeypatch.setattr(atomic.os, "fsync", _no_space)  # the disk fills mid-write
    config.general.theme = "light"
    config.general.house_header = "x" * 10_000
    problem = config.save()

    assert isinstance(problem, NotSaved)
    assert problem.path == config.path
    assert problem.reason == f"cannot be written ({os.strerror(errno.ENOSPC)})"
    assert config.path.read_bytes() == before
    assert load_config().general.board == "aqa"
    assert sorted(p.name for p in config.path.parent.iterdir()) == ["config.toml"]
    assert config.general.theme == "light"  # still applies for the session


def test_saving_keeps_the_config_file_mode(isolated_home: Path) -> None:
    config = load_config()
    assert config.save() is None
    config.path.chmod(0o600)
    config.general.board = "aqa"
    assert config.save() is None
    assert stat.S_IMODE(config.path.stat().st_mode) == 0o600
    assert load_config().general.board == "aqa"


def test_screenshot_day_is_never_read_from_or_written_to_the_file(isolated_home: Path) -> None:
    """Only ``staffroom --screenshot --today`` sets it, for one process: a
    config file can never pin the day a teacher's launcher shows."""
    from datetime import date

    paths.config_file().parent.mkdir(parents=True)
    paths.config_file().write_text(
        'screenshot_day = "2001-01-01"\n[general]\nscreenshot_day = "2001-01-01"\n'
    )
    cfg = load_config()
    assert cfg.screenshot_day is None
    cfg.screenshot_day = date(2026, 10, 9)
    assert cfg.save() is None  # written, through the atomic writer (#125)
    assert "screenshot_day" not in cfg.path.read_text()
    assert load_config().screenshot_day is None
