"""Where things live on disk. Two environment variables redirect the two
folders a run can write to, so tests, the screenshot script and a
contributor's try-out never touch a teacher's real ones:

* ``STAFFROOM_HOME`` replaces ``~/.config/staffroom`` (config, logs, the
  library index, usage);
* ``STAFFROOM_SESSIONS`` replaces the default sessions folder
  (``~/TeachingSessions``: lesson copies and ``outputs/<tool>``), but only
  while Settings leaves the sessions folder empty. A folder the teacher chose
  always wins.

A teacher sets neither, and gets exactly the defaults."""

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
SESSIONS_ENV = "STAFFROOM_SESSIONS"


def sessions_root(configured: str) -> Path:
    """Where ``classroom`` keeps lesson copies. Local by default; the user may
    point it anywhere in Settings. Never auto-detected from cloud folders.

    Order: the folder set in Settings; else ``$STAFFROOM_SESSIONS`` (tests and
    throwaway runs, see the module docstring); else ``~/TeachingSessions``."""
    override = os.environ.get(SESSIONS_ENV, "")
    return Path(configured or override or DEFAULT_SESSIONS_ROOT).expanduser()


def default_sessions_label() -> str:
    """The default sessions folder as Settings names it: ``~/TeachingSessions``
    as written (never the expanded home path), or ``$STAFFROOM_SESSIONS``
    when that is set. Computes nothing on disk."""
    return os.environ.get(SESSIONS_ENV, "") or DEFAULT_SESSIONS_ROOT


OUTPUTS_SUBDIR = "outputs"


def fallback_output_dir(sessions_root_setting: str = "", tool: str = "") -> Path:
    """The one predictable place outputs go when nothing better applies:
    ``<sessions_root>/outputs/<tool>``. Stable across runs, never the process's
    current directory (which for the Dock launcher is the code checkout)."""
    folder = sessions_root(sessions_root_setting) / OUTPUTS_SUBDIR
    return folder / tool if tool else folder


def default_output_dir(
    input_path: Path | None,
    configured: str,
    *,
    resources_root: str = "",
    sessions_root: str = "",
    tool: str = "",
) -> Path:
    """Resolve where a tool should write, in this order:

    1. the folder the teacher configured in Settings, if any;
    2. next to the input file, when there is one and it is not inside the
       read-only resources folder;
    3. otherwise :func:`fallback_output_dir`, ``<sessions_root>/outputs/<tool>``.

    Never the current working directory. Writers create the folder on first
    write, so this function does no I/O."""
    if configured:
        return Path(configured).expanduser()
    if input_path is not None and not (
        resources_root and _is_under(input_path, Path(resources_root).expanduser())
    ):
        return input_path.parent
    return fallback_output_dir(sessions_root, tool)


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True
