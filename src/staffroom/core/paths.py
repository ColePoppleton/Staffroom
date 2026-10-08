"""Where things live on disk. Everything hangs off one root so tests can
redirect it with the ``STAFFROOM_HOME`` environment variable."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

APP_NAME = "staffroom"
# The name before the rename to Staffroom; its config folder is copied once.
LEGACY_APP_NAME = "teaching-tools"


def home_dir() -> Path:
    override = os.environ.get("STAFFROOM_HOME")
    if override:
        return Path(override).expanduser()
    home = Path.home() / ".config" / APP_NAME
    migrate_legacy_home(home)
    return home


def legacy_home_dir() -> Path:
    return Path.home() / ".config" / LEGACY_APP_NAME


def migrate_legacy_home(home: Path | None = None) -> bool:
    """One-time rename migration: copy ``~/.config/teaching-tools/`` to the new
    home when the new one does not exist yet and the old one does. The old
    folder is left in place so an older checkout keeps working. Returns True
    when a copy was made. Cheap enough to run on every ``home_dir()`` call:
    two stats, and nothing once the new folder exists."""
    target = home if home is not None else Path.home() / ".config" / APP_NAME
    legacy = legacy_home_dir()
    if target.exists() or not legacy.is_dir():
        return False
    try:
        shutil.copytree(legacy, target, symlinks=True)
    except OSError:
        return False
    return True


def config_file() -> Path:
    return home_dir() / "config.toml"


def log_dir() -> Path:
    return home_dir() / "logs"


def log_file() -> Path:
    return log_dir() / f"{APP_NAME}.log"


def project_root() -> Path:
    """The repository root (two levels above the ``staffroom`` package)."""
    return Path(__file__).resolve().parents[3]


def examples_dir() -> Path:
    return project_root() / "examples"


DEFAULT_SESSIONS_ROOT = "~/TeachingSessions"


def sessions_root(configured: str) -> Path:
    """Where ``classroom`` keeps lesson copies. Local by default; the user may
    point it anywhere in Settings. Never auto-detected from cloud folders."""
    return Path(configured or DEFAULT_SESSIONS_ROOT).expanduser()


OUTPUTS_SUBDIR = "outputs"


def default_output_dir(
    input_path: Path | None, configured: str, *, resources_root: str = ""
) -> Path:
    """Resolve where a tool should write: the configured folder if set,
    otherwise alongside the input, otherwise the current directory.

    The resources folder is read-only to every tool, so an input that lives
    under ``resources_root`` sends outputs to ``<sessions_root>/outputs``
    instead of next to the file."""
    if configured:
        return Path(configured).expanduser()
    if input_path is not None:
        if resources_root and _is_under(input_path, Path(resources_root).expanduser()):
            return sessions_root("") / OUTPUTS_SUBDIR
        return input_path.parent
    return Path.cwd()


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True
