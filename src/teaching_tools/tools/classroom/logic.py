"""Pure logic for classroom: naming, validation and diffing. No I/O."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import date

MAX_LABEL = 60
_UNSAFE = re.compile(r"[^A-Za-z0-9 _.-]+")
_SPACES = re.compile(r"\s+")
_VERSION = re.compile(r"^(?P<stem>.*?)(?:_v(?P<n>\d+))?$")


@dataclass(frozen=True)
class SessionFile:
    """One copy made for a lesson. ``rel_path`` is relative to the sessions
    root (``2026-10-06/P3 Y9 loops/while_loops.py``); ``origin`` is the
    original resource's absolute path as recorded when the copy was made."""

    rel_path: str
    day: str
    label: str
    name: str
    origin: str
    size: int
    mtime: float


def validate_label(label: str) -> str:
    """One short line describing the lesson, e.g. ``P3 Y9 loops``. Never a
    class list or pupil names: the UI says so and the length cap backs it up."""
    text = _SPACES.sub(" ", label).strip()
    if not text:
        msg = "Give the lesson a short label, e.g. 'P3 Y9 loops'."
        raise ValueError(msg)
    if "\n" in label.strip() or len(text) > MAX_LABEL:
        msg = f"The label is one short line (max {MAX_LABEL} characters)."
        raise ValueError(msg)
    return text


def label_folder(label: str) -> str:
    """Filesystem-safe folder name for a label; keeps it readable."""
    cleaned = _UNSAFE.sub("", validate_label(label)).strip(" .")
    return cleaned or "lesson"


def session_folder(day: date, label: str) -> str:
    return f"{day.isoformat()}/{label_folder(label)}"


def promoted_name(name: str, existing: set[str]) -> str:
    """``while.py`` -> ``while_v2.py``; if that exists, ``while_v3.py`` and so
    on. ``while_v2.py`` promotes to ``while_v3.py``. Never returns a name in
    ``existing``."""
    dot = name.rfind(".")
    stem, ext = (name, "") if dot <= 0 else (name[:dot], name[dot:])
    m = _VERSION.match(stem)
    base = m.group("stem") if m and m.group("stem") else stem
    n = int(m.group("n")) + 1 if m and m.group("n") else 2
    while f"{base}_v{n}{ext}" in existing:
        n += 1
    return f"{base}_v{n}{ext}"


def unified_diff(original: str, edited: str, original_name: str, edited_name: str) -> str:
    lines = difflib.unified_diff(
        original.splitlines(keepends=True),
        edited.splitlines(keepends=True),
        fromfile=original_name,
        tofile=edited_name,
    )
    text = "".join(lines)
    return text if text else "No changes: the session copy matches the original."


def summarise_diff(diff: str) -> str:
    lines = diff.splitlines()
    added = sum(1 for ln in lines if ln.startswith("+") and not ln.startswith("+++"))
    removed = sum(1 for ln in lines if ln.startswith("-") and not ln.startswith("---"))
    if not added and not removed:
        return "no changes"
    return f"+{added} / -{removed} lines"
