"""``atomic_write_text`` (#125): a failed write leaves the old file as it was,
no temporary file behind, and the file's permissions unchanged."""

from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

import pytest

from staffroom.core import atomic
from staffroom.core.atomic import atomic_write_text


def _no_space(fd: int) -> None:
    raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))


def test_writes_a_new_file(tmp_path: Path) -> None:
    target = tmp_path / "new.toml"
    atomic_write_text(target, "x = 1\n")
    assert target.read_text(encoding="utf-8") == "x = 1\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["new.toml"]


def test_replaces_an_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("old\n", encoding="utf-8")
    atomic_write_text(target, "new £\n")
    assert target.read_text(encoding="utf-8") == "new £\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.toml"]


def test_a_failed_write_keeps_the_old_file_and_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "config.toml"
    target.write_text("old\n", encoding="utf-8")
    monkeypatch.setattr(atomic.os, "fsync", _no_space)  # after the bytes are written
    with pytest.raises(OSError) as info:
        atomic_write_text(target, "new\n" * 1000)
    assert info.value.errno == errno.ENOSPC
    assert target.read_text(encoding="utf-8") == "old\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.toml"]


def test_a_failed_replace_keeps_the_old_file_and_no_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "config.toml"
    target.write_text("old\n", encoding="utf-8")

    def fail(src: object, dst: object) -> None:
        raise OSError(errno.EIO, os.strerror(errno.EIO))

    monkeypatch.setattr(atomic.os, "replace", fail)
    with pytest.raises(OSError):
        atomic_write_text(target, "new\n")
    assert target.read_text(encoding="utf-8") == "old\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.toml"]


def test_keeps_the_existing_permissions(tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("old\n", encoding="utf-8")
    target.chmod(0o640)
    atomic_write_text(target, "new\n")
    assert stat.S_IMODE(target.stat().st_mode) == 0o640


def test_a_new_file_gets_the_usual_umask_mode(tmp_path: Path) -> None:
    """As ``open(..., "w")`` would: 0o666 less the umask, not mkstemp's 0o600."""
    old = os.umask(0o022)
    try:
        atomic_write_text(tmp_path / "new.toml", "x\n")
    finally:
        os.umask(old)
    assert stat.S_IMODE((tmp_path / "new.toml").stat().st_mode) == 0o644


@pytest.mark.skipif(os.geteuid() == 0, reason="root is not bound by file modes")
def test_a_read_only_file_is_not_replaced(tmp_path: Path) -> None:
    """Renaming over a file ignores its own mode; a file someone made read-only
    stays as it is, as it did when it was opened for writing."""
    target = tmp_path / "config.toml"
    target.write_text("old\n", encoding="utf-8")
    target.chmod(0o400)
    try:
        with pytest.raises(PermissionError) as info:
            atomic_write_text(target, "new\n")
    finally:
        target.chmod(0o600)
    assert info.value.errno == errno.EACCES
    assert target.read_text(encoding="utf-8") == "old\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["config.toml"]


def test_writes_through_a_symlink(tmp_path: Path) -> None:
    """A config kept elsewhere and linked in stays a link to the new contents."""
    real = tmp_path / "dotfiles" / "config.toml"
    real.parent.mkdir()
    real.write_text("old\n", encoding="utf-8")
    link = tmp_path / "config.toml"
    link.symlink_to(real)
    atomic_write_text(link, "new\n")
    assert link.is_symlink()
    assert real.read_text(encoding="utf-8") == "new\n"
    assert sorted(p.name for p in real.parent.iterdir()) == ["config.toml"]


def test_a_missing_folder_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        atomic_write_text(tmp_path / "absent" / "config.toml", "x\n")
