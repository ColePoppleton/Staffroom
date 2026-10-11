"""Logging setup shared by the CLI and the shell.

The shell attaches an extra handler that feeds its log drawer; the CLI gets
stderr only with ``staff -v`` (#20), because each command already prints a plain
line for anything the teacher needs to know. Both also write to a rotating file
under the config directory when that directory can be written; when it cannot,
they carry on with stderr.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TextIO

from staffroom.core import paths

ROOT_LOGGER = "staffroom"
FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DATEFMT = "%H:%M:%S"


class _StderrHandler(logging.StreamHandler):  # type: ignore[type-arg,unused-ignore]
    """Writes to whatever ``sys.stderr`` is *now*. The plain StreamHandler
    captures the stream once, which breaks under test runners that swap
    and close stderr (typer's CliRunner)."""

    def __init__(self) -> None:
        super().__init__(sys.stderr)

    @property
    def stream(self) -> TextIO:
        return sys.stderr

    @stream.setter
    def stream(self, _value: TextIO) -> None:
        pass


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{ROOT_LOGGER}.{name}" if not name.startswith(ROOT_LOGGER) else name)


def setup_logging(
    level: str = "INFO", *, log_file: Path | None = None, stderr: bool = True
) -> Path | None:
    """Idempotent: calling twice replaces the handlers rather than doubling them.

    Returns the log file in use, or ``None`` when it could not be opened. A
    config home that cannot be written (a locked-down school account, #60)
    must never stop a command: logging then falls back to stderr alone, with
    one warning line saying so. The launcher asks for no stderr handler; in
    the fallback it gets one anyway, or the warning would have nowhere to go.
    """
    logger = logging.getLogger(ROOT_LOGGER)
    logger.setLevel(level.upper())
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    formatter = logging.Formatter(FORMAT, DATEFMT)
    if stderr:
        logger.addHandler(_stderr_handler(formatter))
    log_file = log_file or paths.log_file()
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(log_file, maxBytes=512_000, backupCount=3, encoding="utf-8")
    except OSError as exc:
        if not stderr:
            logger.addHandler(_stderr_handler(formatter))
        logger.warning(
            "Cannot open the log file %s (%s); logging to stderr only for this run",
            log_file,
            exc.strerror or exc,
        )
        return None
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    return log_file


def _stderr_handler(formatter: logging.Formatter) -> logging.Handler:
    sh = _StderrHandler()
    sh.setFormatter(formatter)
    return sh
