"""File operations for classroom: make lesson copies, remember where they
came from, list them, diff them, promote them. The resources root is only
ever read, except by :func:`promote`, which adds a new file and never
overwrites one."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from staffroom.core.launch import Runner, launch_editor
from staffroom.core.log import get_logger
from staffroom.core.table import Row, Table
from staffroom.tools.classroom.logic import (
    SessionFile,
    latest_version,
    promoted_name,
    session_folder,
    unified_diff,
    validate_label,
)

log = get_logger(__name__)
ORIGIN_FILE = ".origin.json"


# ---------------------------------------------------------------- origin sidecar
def _read_origins(folder: Path) -> dict[str, str]:
    path = folder / ORIGIN_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: str(v) for k, v in data.get("files", {}).items()}


def _write_origin(folder: Path, name: str, origin: Path, label: str) -> None:
    path = folder / ORIGIN_FILE
    data = _read_origins(folder)
    data[name] = str(origin)
    payload = {"label": label, "files": data}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _read_label(folder: Path) -> str:
    path = folder / ORIGIN_FILE
    try:
        return str(json.loads(path.read_text(encoding="utf-8")).get("label", folder.name))
    except (OSError, ValueError):
        return folder.name


# ---------------------------------------------------------------- operations
def open_for_class(
    resource: Path,
    label: str,
    sessions_root: Path,
    editor_command: str,
    *,
    today: date | None = None,
    runner: Runner | None = None,
) -> tuple[Path, bool]:
    """Copy ``resource`` into today's session folder for ``label`` and launch
    the editor on the copy. Returns ``(copy, created)``; an existing copy is
    re-opened rather than overwritten so edits are never lost."""
    if not resource.is_file():
        msg = f"Not a file: {resource}"
        raise FileNotFoundError(msg)
    label = validate_label(label)
    folder = sessions_root / session_folder(today or date.today(), label)
    folder.mkdir(parents=True, exist_ok=True)
    copy = folder / resource.name
    created = not copy.exists()
    if created:
        shutil.copy2(resource, copy)
        _write_origin(folder, resource.name, resource.resolve(), label)
        log.info("copied %s -> %s", resource, copy)
    launch_editor(editor_command, copy, runner)
    return copy, created


def list_sessions(sessions_root: Path) -> list[SessionFile]:
    """Every lesson copy under the root, newest day first."""
    found: list[SessionFile] = []
    if not sessions_root.is_dir():
        return found
    for day_dir in sorted(sessions_root.iterdir(), reverse=True):
        if not day_dir.is_dir() or day_dir.name.startswith("."):
            continue
        for label_dir in sorted(day_dir.iterdir()):
            if not label_dir.is_dir() or label_dir.name.startswith("."):
                continue
            origins = _read_origins(label_dir)
            label = _read_label(label_dir)
            for file in sorted(label_dir.iterdir()):
                if not file.is_file() or file.name.startswith("."):
                    continue
                st = file.stat()
                found.append(
                    SessionFile(
                        rel_path=file.relative_to(sessions_root).as_posix(),
                        day=day_dir.name,
                        label=label,
                        name=file.name,
                        origin=origins.get(file.name, ""),
                        size=st.st_size,
                        mtime=st.st_mtime,
                    )
                )
    return found


def sessions_table(files: list[SessionFile]) -> Table:
    rows: list[Row] = [
        [
            f.day,
            f.label,
            f.name,
            datetime.fromtimestamp(f.mtime).strftime("%d %b %H:%M"),
            f.origin,
            f.rel_path,
        ]
        for f in files
    ]
    return Table(["Date", "Lesson", "File", "Edited", "Original", "Session file"], rows)


def resolve_session_file(sessions_root: Path, ref: str | Path) -> Path:
    """Accept a path relative to the sessions root or an absolute path."""
    p = Path(ref).expanduser()
    if not p.is_absolute():
        p = sessions_root / p
    if not p.is_file():
        msg = f"No such session file: {ref}"
        raise FileNotFoundError(msg)
    return p


def origin_of(session_file: Path) -> Path | None:
    origin = _read_origins(session_file.parent).get(session_file.name)
    return Path(origin) if origin else None


def diff_against_original(session_file: Path) -> str:
    origin = origin_of(session_file)
    if origin is None:
        return f"No origin recorded for {session_file.name}; it was not made by classroom."
    if not origin.exists():
        return f"The original has gone: {origin}"
    try:
        a = origin.read_text(encoding="utf-8", errors="replace")
        b = session_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Could not read: {exc}"
    return unified_diff(a, b, f"original/{origin.name}", f"session/{session_file.name}")


@dataclass(frozen=True)
class Promotion:
    """What :func:`promote` did. ``created`` is False when nothing was written
    because the copy is byte-identical to ``target``: the original itself
    (``matches_original``, nothing to promote) or the latest promoted version
    (already promoted)."""

    target: Path
    created: bool
    matches_original: bool = False

    @property
    def summary(self) -> str:
        if self.created:
            return f"Promoted as {self.target.name} next to the original"
        if self.matches_original:
            return (
                f"No changes: the copy matches the original {self.target.name}; nothing to promote"
            )
        return f"Already promoted as {self.target.name}: the copy has not changed since"


def _same_bytes(a: Path, b: Path) -> bool:
    try:
        return a.is_file() and b.is_file() and a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def promote(session_file: Path, resources_root: Path) -> Promotion:
    """Copy the edited session file back next to its original under a new
    versioned name. Never overwrites; the original is untouched. A copy that
    is byte-identical to the original, or to the latest promoted version, is
    not written again: the result says which file already holds it."""
    origin = origin_of(session_file)
    if origin is None:
        msg = f"No origin recorded for {session_file.name}; promote by hand."
        raise ValueError(msg)
    target_dir = origin.parent if origin.parent.exists() else resources_root
    if _same_bytes(session_file, origin):
        log.info("not promoted: %s matches its original %s", session_file, origin)
        return Promotion(origin, created=False, matches_original=True)
    existing = {p.name for p in target_dir.iterdir()}
    latest = latest_version(origin.name, existing)
    if latest is not None and _same_bytes(session_file, target_dir / latest):
        log.info("not promoted: %s already promoted as %s", session_file, latest)
        return Promotion(target_dir / latest, created=False)
    target = target_dir / promoted_name(origin.name, existing)
    shutil.copy2(session_file, target)
    log.info("promoted %s -> %s", session_file, target)
    return Promotion(target, created=True)


def reopen(session_file: Path, editor_command: str, runner: Runner | None = None) -> list[str]:
    return launch_editor(editor_command, session_file, runner)
