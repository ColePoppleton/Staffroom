"""The exclusion list: folders and files under the resources root that the
library must neither index nor list.

Patterns come from two places and are merged: ``[general] library_exclude``
in the config (edited in Settings or with ``staff library exclude``) and an
optional ``<root>/.staffroom/ignore`` file, one pattern per line, ``#`` for
comments, for a folder shared between machines. The resources root itself is
never written: the ignore file is read, not created, by the app.

A pattern is either a *name* (no ``/``): it matches any folder or file with
that name at any depth, with ``*`` and ``?`` wildcards (``Pupil work``,
``*assessment*``, ``*.bak``); or a *path* (contains ``/``): it matches from
the root (``Year 11/Mocks``, ``*/submissions``). ``*`` and ``?`` never cross
a ``/``; ``**`` matches any number of folders. A trailing ``/`` is allowed
and ignored. Matching is case-insensitive, as macOS file names are.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path, PurePosixPath

from staffroom.core.library.tags import LEGACY_SIDECAR_DIR, SIDECAR_DIR

IGNORE_FILE = "ignore"


def ignore_file_path(root: Path) -> Path:
    return root / SIDECAR_DIR / IGNORE_FILE


def normalise_patterns(patterns: Iterable[str]) -> list[str]:
    """Strip, drop blanks and comments, remove leading ``./`` and trailing
    ``/``, convert backslashes, de-duplicate keeping order."""
    seen: dict[str, None] = {}
    for raw in patterns:
        p = raw.strip().replace("\\", "/")
        if not p or p.startswith("#"):
            continue
        p = p.removeprefix("./").strip("/")
        if p:
            seen.setdefault(p, None)
    return list(seen)


def read_ignore_file(root: Path) -> list[str]:
    """Patterns from ``<root>/.staffroom/ignore`` (or the legacy
    ``.teaching-tools/ignore``); empty when there is none or it is unreadable."""
    for folder in (SIDECAR_DIR, LEGACY_SIDECAR_DIR):
        path = root / folder / IGNORE_FILE
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        return normalise_patterns(text.splitlines())
    return []


def glob_to_regex(pattern: str) -> str:
    """``*`` and ``?`` match within one path segment; ``**`` spans segments."""
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "*":
            if pattern.startswith("**", i):
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return "".join(out) + r"\Z"


class ExclusionList:
    """Compiled patterns with a single question: is this relative path out?"""

    def __init__(self, patterns: Iterable[str] = ()) -> None:
        self.patterns = normalise_patterns(patterns)
        self._names: list[re.Pattern[str]] = []
        self._paths: list[re.Pattern[str]] = []
        for p in self.patterns:
            compiled = re.compile(glob_to_regex(p), re.IGNORECASE)
            (self._paths if "/" in p else self._names).append(compiled)

    def __bool__(self) -> bool:
        return bool(self.patterns)

    def __len__(self) -> int:
        return len(self.patterns)

    def matches(self, rel_path: str | PurePosixPath) -> bool:
        """True when ``rel_path`` (POSIX, relative to the root) or any folder
        above it is excluded. ``""`` (the root itself) never is."""
        rel = PurePosixPath(str(rel_path).replace("\\", "/"))
        parts = [p.lower() for p in rel.parts if p not in ("", ".")]
        if not parts:
            return False
        if self._names and any(n.match(part) for part in parts for n in self._names):
            return True
        if self._paths:
            for depth in range(1, len(parts) + 1):
                prefix = "/".join(parts[:depth])
                if any(p.match(prefix) for p in self._paths):
                    return True
        return False

    @classmethod
    def for_root(cls, root: Path, configured: Iterable[str] = ()) -> ExclusionList:
        """Configured patterns plus the root's ignore file."""
        return cls([*configured, *read_ignore_file(root)])
