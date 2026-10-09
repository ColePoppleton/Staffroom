"""Logging must never stop a command. When the config home cannot be written
(a locked-down school account, a home on read-only media), ``setup_logging``
falls back to stderr alone and says so in one warning line (#60)."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core import paths
from staffroom.core.log import ROOT_LOGGER, setup_logging

runner = CliRunner()

pytestmark = pytest.mark.skipif(os.geteuid() == 0, reason="root is not bound by file modes")


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


def _handlers() -> list[logging.Handler]:
    return list(logging.getLogger(ROOT_LOGGER).handlers)


def test_writable_home_gets_a_log_file(isolated_home: Path) -> None:
    assert setup_logging("INFO") == paths.log_file()
    assert paths.log_file().exists()
    assert any(isinstance(h, RotatingFileHandler) for h in _handlers())


def test_read_only_home_falls_back_to_stderr_with_one_warning(
    read_only_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert setup_logging("INFO") is None
    assert not paths.log_dir().exists()
    handlers = _handlers()
    assert len(handlers) == 1 and not isinstance(handlers[0], RotatingFileHandler)
    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1, lines
    assert "WARNING" in lines[0] and str(paths.log_file()) in lines[0]
    assert "stderr" in lines[0]


def test_launcher_setup_without_stderr_still_warns_once(
    read_only_home: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The launcher asks for no stderr handler (its log drawer attaches its
    own). With no file either, nothing would be left: the fallback adds stderr
    so the warning, and later messages, go somewhere."""
    assert setup_logging("INFO", stderr=False) is None
    assert len(_handlers()) == 1
    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1 and "WARNING" in lines[0], lines


@pytest.mark.parametrize("argv", [["version"], ["list"]])
def test_cli_exit_code_and_output_do_not_change_with_a_read_only_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> None:
    """The acceptance criterion from #60: a ``chmod 0o500`` home changes
    neither the exit code nor stdout; the only difference is one warning line
    on stderr. The two runs use separate homes so the writable run cannot
    leave a ``logs/`` folder that the read-only run would then reuse."""
    monkeypatch.setenv("STAFFROOM_HOME", str(tmp_path / "writable"))
    expected = runner.invoke(app, argv)
    assert expected.exit_code == 0, expected.output

    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        monkeypatch.setenv("STAFFROOM_HOME", str(locked))
        actual = runner.invoke(app, argv)
    finally:
        locked.chmod(0o700)

    assert actual.exit_code == expected.exit_code, actual.output
    assert actual.stdout == expected.stdout
    assert actual.exception is None or isinstance(actual.exception, SystemExit)
    assert "Traceback" not in actual.output and "PermissionError" not in actual.output
    assert actual.stderr.count("WARNING") == 1 and str(locked) in actual.stderr
    assert not (locked / "logs").exists()


def test_tool_still_runs_with_a_read_only_home(
    read_only_home: Path, example_marks: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    result = runner.invoke(app, ["hello", "run", str(example_marks), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert (out / "marks_10x_totals.csv").exists()
    assert "Traceback" not in result.output
    assert not (read_only_home / "logs").exists()
    assert not (read_only_home / "usage.toml").exists()  # #28's quiet skip still holds
