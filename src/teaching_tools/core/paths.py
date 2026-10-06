"""Where things live on disk. Everything hangs off one root so tests can
redirect it with the ``TEACHING_TOOLS_HOME`` environment variable."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "teaching-tools"


def home_dir() -> Path:
    override = os.environ.get("TEACHING_TOOLS_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / APP_NAME


def config_file() -> Path:
    return home_dir() / "config.toml"


def log_dir() -> Path:
    return home_dir() / "logs"


def log_file() -> Path:
    return log_dir() / f"{APP_NAME}.log"


def project_root() -> Path:
    """The repository root (two levels above the ``teaching_tools`` package)."""
    return Path(__file__).resolve().parents[3]


def examples_dir() -> Path:
    return project_root() / "examples"


DEFAULT_SESSIONS_ROOT = "~/TeachingSessions"


def sessions_root(configured: str) -> Path:
    """Where ``classroom`` keeps lesson copies. Local by default; the user may
    point it anywhere in Settings. Never auto-detected from cloud folders."""
    return Path(configured or DEFAULT_SESSIONS_ROOT).expanduser()


def default_output_dir(input_path: Path | None, configured: str) -> Path:
    """Resolve where a tool should write: the configured folder if set,
    otherwise alongside the input, otherwise the current directory."""
    if configured:
        return Path(configured).expanduser()
    if input_path is not None:
        return input_path.parent
    return Path.cwd()
