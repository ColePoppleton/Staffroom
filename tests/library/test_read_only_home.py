"""The Resource Library must never stop the app. When the config home cannot
be written (``chmod 0o500``, a locked-down school account, #65) ``LibraryDB``
opens what it can: the last index read-only when the file is there, an empty
in-memory database otherwise. The service says why in one warning line, the
sidebar and ``staff library status`` repeat it, and every tool still runs."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import load_config
from staffroom.core.library.db import LibraryDB
from staffroom.core.library.service import LibraryService, library_db_path

runner = CliRunner()

pytestmark = pytest.mark.skipif(os.geteuid() == 0, reason="root is not bound by file modes")

UNAVAILABLE = "Resource Library unavailable: cannot write "


@pytest.fixture
def read_only_home(isolated_home: Path) -> Iterator[Path]:
    """The isolated home, created empty and made read-only (``0o500``) for the
    test. Permissions are restored on teardown so pytest can clean ``tmp_path``."""
    isolated_home.mkdir(parents=True)
    isolated_home.chmod(0o500)
    try:
        yield isolated_home
    finally:
        isolated_home.chmod(0o700)


@pytest.fixture
def locked_home_with_root(isolated_home: Path, resources_root: Path) -> Iterator[Path]:
    """A home whose config names a resources folder, then locked: the CLI can
    read the config but write nothing under the home."""
    cfg = load_config()
    cfg.general.resources_root = str(resources_root)
    cfg.save()
    isolated_home.chmod(0o500)
    try:
        yield isolated_home
    finally:
        isolated_home.chmod(0o700)


class _Records(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


# ---------------------------------------------------------------- LibraryDB
def test_missing_database_in_a_locked_home_falls_back_to_memory(read_only_home: Path) -> None:
    path = read_only_home / "library.db"
    db = LibraryDB(path)
    try:
        assert db.mode == "memory" and not db.writable
        assert db.problem is not None and db.problem.startswith(UNAVAILABLE)
        assert str(path) in db.problem
        assert db.count() == 0 and db.search("while") == [] and db.get_meta("x") is None
    finally:
        db.close()
    assert not path.exists()


def test_writable_home_is_unchanged(isolated_home: Path) -> None:
    db = LibraryDB(isolated_home / "library.db")
    try:
        assert db.mode == "read-write" and db.writable and db.problem is None
    finally:
        db.close()
    assert (isolated_home / "library.db").exists()


def test_existing_database_in_a_locked_home_opens_read_only(
    tmp_path: Path, resources_root: Path
) -> None:
    """The last index is still searchable; only updating it is impossible."""
    home = tmp_path / "home"
    home.mkdir()
    db_path = home / "library.db"
    svc = LibraryService(resources_root, db_path)
    svc.index()
    indexed = svc.counts().indexed
    svc.close()
    home.chmod(0o500)
    try:
        svc = LibraryService(resources_root, db_path)
        try:
            assert svc.db.mode == "read-only" and not svc.available
            assert svc.unavailable_reason is not None and svc.unavailable_reason.startswith(
                UNAVAILABLE
            )
            assert svc.counts().indexed == indexed > 0
            assert svc.last_indexed() is not None
            assert any(h.resource.name == "while_loops.py" for h in svc.search("while"))
            with pytest.raises(PermissionError, match="cannot write"):
                svc.index()
        finally:
            svc.close()
    finally:
        home.chmod(0o700)


def test_unreadable_schema_in_a_locked_home_falls_back_to_memory(tmp_path: Path) -> None:
    """A file that is not our database (or an older schema we cannot migrate
    without writing) is left alone and the session runs on an empty one."""
    home = tmp_path / "home"
    home.mkdir()
    (home / "library.db").write_bytes(b"not a database at all\n")
    home.chmod(0o500)
    try:
        db = LibraryDB(home / "library.db")
        try:
            assert db.mode == "memory" and not db.writable
            assert db.count() == 0
        finally:
            db.close()
    finally:
        home.chmod(0o700)


# ---------------------------------------------------------------- LibraryService
def test_service_logs_the_reason_once(read_only_home: Path) -> None:
    handler = _Records()
    logger = logging.getLogger("staffroom.core.library.service")
    logger.addHandler(handler)
    try:
        svc = LibraryService(Path(""))
        try:
            svc.counts()
            svc.search("loops")
            svc.resources()
        finally:
            svc.close()
    finally:
        logger.removeHandler(handler)
    warnings = [r.getMessage() for r in handler.records if r.levelno >= logging.WARNING]
    assert len(warnings) == 1, warnings
    assert warnings[0].startswith(UNAVAILABLE) and str(library_db_path()) in warnings[0]


def test_available_service_has_no_reason(isolated_home: Path, resources_root: Path) -> None:
    svc = LibraryService(resources_root)
    try:
        assert svc.available and svc.unavailable_reason is None
    finally:
        svc.close()


# ---------------------------------------------------------------- CLI
def test_library_status_exits_zero_with_a_clear_line(locked_home_with_root: Path) -> None:
    r = runner.invoke(app, ["library", "status"])
    assert r.exit_code == 0, r.output
    assert "Traceback" not in r.output and "OperationalError" not in r.output
    lines = [line for line in r.stdout.splitlines() if line.startswith(UNAVAILABLE)]
    assert len(lines) == 1, r.stdout
    assert str(library_db_path()) in lines[0]
    assert "files:       0 indexed" in r.stdout
    assert "last index:  never" in r.stdout


def test_library_index_exits_one_with_the_reason(locked_home_with_root: Path) -> None:
    r = runner.invoke(app, ["library", "index"])
    assert r.exit_code == 1, r.output
    assert "Traceback" not in r.output
    assert UNAVAILABLE in r.stderr and str(library_db_path()) in r.stderr
    assert not (locked_home_with_root / "library.db").exists()


def test_library_search_says_unavailable_not_empty(locked_home_with_root: Path) -> None:
    """``index is empty; run staff library index`` would send the teacher to
    a command that cannot work; the reason comes first."""
    r = runner.invoke(app, ["library", "search", "while"])
    assert r.exit_code == 1, r.output
    assert UNAVAILABLE in r.stderr
    assert "index is empty" not in r.output


def test_tools_still_run(read_only_home: Path, example_marks: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    r = runner.invoke(app, ["hello", "run", str(example_marks), "--out", str(out)])
    assert r.exit_code == 0, r.output
    assert (out / "marks_10x_summary.csv").exists()


def test_library_exclude_with_a_locked_config_exits_one_with_the_reason(
    locked_home_with_root: Path,
) -> None:
    """``Config.save`` returns what went wrong instead of raising (#74); the
    CLI still turns it into one red line and exit code 1."""
    config_file = locked_home_with_root / "config.toml"
    config_file.chmod(0o400)
    try:
        r = runner.invoke(app, ["library", "exclude", "--add", "Pupil work"])
    finally:
        config_file.chmod(0o600)
    assert r.exit_code == 1, r.output
    assert "Traceback" not in r.output
    assert f"cannot save {config_file}: it is read-only" in r.stderr
    assert "Pupil work" not in load_config().general.library_exclude
