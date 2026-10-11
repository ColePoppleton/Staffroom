"""Saving the config under a read-only config home (#74). ``Config.save``
never raises ``OSError``: it returns a :class:`NotSaved` the caller can show
the teacher, logs one warning per session, and the change stays in memory."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from staffroom.core.config import Config, NotSaved, load_config

pytestmark = pytest.mark.skipif(os.geteuid() == 0, reason="root is not bound by file modes")


class Records(logging.Handler):
    """Not caplog: ``setup_logging`` stops the "staffroom" logger propagating."""

    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


@pytest.fixture
def config_records() -> Iterator[Records]:
    records = Records()
    logger = logging.getLogger("staffroom.core.config")
    logger.addHandler(records)
    try:
        yield records
    finally:
        logger.removeHandler(records)


@pytest.fixture
def locked_config(isolated_home: Path) -> Iterator[Config]:
    """A saved ``config.toml`` at ``0o400`` in a ``0o500`` home, restored on
    teardown so pytest can clean ``tmp_path``."""
    config = load_config()
    assert config.save() is None
    config.path.chmod(0o400)
    isolated_home.chmod(0o500)
    try:
        yield config
    finally:
        isolated_home.chmod(0o700)
        config.path.chmod(0o600)


def test_a_writable_home_saves_and_returns_none(isolated_home: Path) -> None:
    config = load_config()
    config.general.board = "aqa"
    assert config.save() is None
    assert load_config().general.board == "aqa"


def test_a_locked_config_returns_the_teacher_message(locked_config: Config) -> None:
    locked_config.general.board = "aqa"
    problem = locked_config.save()
    assert isinstance(problem, NotSaved)
    assert problem.path == locked_config.path and problem.reason == "is read-only"
    assert str(problem) == (
        f"Settings could not be saved: {locked_config.path} is read-only. "
        "Changes last until you quit."
    )
    assert locked_config.general.board == "aqa"  # still applies for the session
    assert load_config().general.board == "ocr"  # the file is untouched


def test_a_locked_home_without_a_config_file_does_not_raise(isolated_home: Path) -> None:
    isolated_home.mkdir(parents=True)
    isolated_home.chmod(0o500)
    try:
        problem = load_config().save()
    finally:
        isolated_home.chmod(0o700)
    assert problem is not None and problem.reason == "is read-only"


def test_one_warning_per_session_however_many_saves(
    locked_config: Config, config_records: Records
) -> None:
    for theme in ("light", "dark", "light"):
        locked_config.general.theme = theme  # type: ignore[assignment]
        assert locked_config.save() is not None
    warnings = [m for m in config_records.messages if m.startswith("Cannot save ")]
    assert len(warnings) == 1, config_records.messages
    assert str(locked_config.path) in warnings[0]


def test_other_write_errors_name_the_reason(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("")
    problem = Config(path=blocker / "config.toml").save()  # parent is a file
    assert problem is not None
    assert problem.reason.startswith("cannot be written (")
    assert "Changes last until you quit." in str(problem)
