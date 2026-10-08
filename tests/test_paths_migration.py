"""Renaming to Staffroom must not lose a teacher's settings: the first run
copies ``~/.config/teaching-tools/`` to ``~/.config/staffroom/`` and leaves
the old folder alone."""

from __future__ import annotations

from pathlib import Path

import pytest

from staffroom.core import paths


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("STAFFROOM_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


def test_legacy_home_is_copied_once(fake_home: Path) -> None:
    legacy = fake_home / ".config" / "teaching-tools"
    (legacy / "logs").mkdir(parents=True)
    (legacy / "config.toml").write_text('[general]\ntheme = "light"\n')
    (legacy / "logs" / "teaching-tools.log").write_text("old log\n")

    home = paths.home_dir()

    assert home == fake_home / ".config" / "staffroom"
    assert (home / "config.toml").read_text() == '[general]\ntheme = "light"\n'
    assert (home / "logs" / "teaching-tools.log").exists()
    assert legacy.is_dir(), "the old folder is left for an older checkout"

    # Once the new home exists it is never overwritten by the old one again.
    (home / "config.toml").write_text("changed\n")
    (legacy / "config.toml").write_text("stale\n")
    assert paths.home_dir() == home
    assert (home / "config.toml").read_text() == "changed\n"
    assert paths.migrate_legacy_home() is False


def test_fresh_install_has_nothing_to_migrate(fake_home: Path) -> None:
    home = paths.home_dir()
    assert home == fake_home / ".config" / "staffroom"
    assert not home.exists()
    assert paths.migrate_legacy_home() is False


def test_env_override_skips_migration(
    fake_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = fake_home / ".config" / "teaching-tools"
    legacy.mkdir(parents=True)
    (legacy / "config.toml").write_text("x = 1\n")
    override = tmp_path / "elsewhere"
    monkeypatch.setenv("STAFFROOM_HOME", str(override))
    assert paths.home_dir() == override
    assert not (fake_home / ".config" / "staffroom").exists()
