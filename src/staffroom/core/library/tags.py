"""Tags and notes per resource, kept in a sidecar JSON file inside the root:
``<root>/.staffroom/tags.json``. Resource files are never written. A sidecar
left by the app under its old name (``.teaching-tools``) is still read; the
next save writes the new location."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path

SIDECAR_DIR = ".staffroom"
LEGACY_SIDECAR_DIR = ".teaching-tools"
SIDECAR_FILE = "tags.json"


@dataclass
class TagEntry:
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def empty(self) -> bool:
        return not self.tags and not self.notes.strip()


def normalise_tags(tags: list[str] | str) -> list[str]:
    raw = tags.split(",") if isinstance(tags, str) else tags
    seen: dict[str, None] = {}
    for t in raw:
        t = t.strip().lower()
        if t:
            seen.setdefault(t, None)
    return list(seen)


@dataclass(frozen=True)
class TagCount:
    """A tag in use and how many files carry it."""

    tag: str
    count: int

    @property
    def label(self) -> str:
        """``loops  3``: how the Library's tag filter lists it."""
        return f"{self.tag}  {self.count}"


def count_tags(
    tags_by_path: Mapping[str, Iterable[str]], within: Iterable[str] | None = None
) -> list[TagCount]:
    """The tags in use, most-used first, then by name. ``within`` limits the
    count to those paths (the files the Library lists), so a sidecar entry
    for a file that is gone or excluded does not count."""
    allowed = None if within is None else set(within)
    counts: dict[str, int] = {}
    for rel, tags in tags_by_path.items():
        if allowed is not None and rel not in allowed:
            continue
        for t in tags:
            counts[t] = counts.get(t, 0) + 1
    return [TagCount(t, n) for t, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


def paths_with_tags(tags_by_path: Mapping[str, Iterable[str]], chosen: Iterable[str]) -> set[str]:
    """The paths carrying every chosen tag (each choice narrows further).
    Choices are normalised the way the sidecar stores tags."""
    wanted = set(normalise_tags(list(chosen)))
    return {rel for rel, tags in tags_by_path.items() if wanted <= set(tags)}


class TagStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.path = root / SIDECAR_DIR / SIDECAR_FILE
        self._legacy_path = root / LEGACY_SIDECAR_DIR / SIDECAR_FILE
        self._entries: dict[str, TagEntry] = {}
        self.load()

    # -- persistence -----------------------------------------------------
    def load(self) -> None:
        self._entries = {}
        source = self.path if self.path.exists() else self._legacy_path
        if not source.exists():
            return
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for rel, entry in raw.get("entries", {}).items():
            if isinstance(entry, dict):
                self._entries[rel] = TagEntry(
                    tags=normalise_tags(list(entry.get("tags", []))),
                    notes=str(entry.get("notes", "")),
                )

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "entries": {rel: asdict(e) for rel, e in sorted(self._entries.items()) if not e.empty},
        }
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)
        return self.path

    # -- access ----------------------------------------------------------
    def get(self, rel_path: str) -> TagEntry:
        entry = self._entries.get(rel_path)
        return TagEntry(list(entry.tags), entry.notes) if entry else TagEntry()

    def set_entry(self, rel_path: str, tags: list[str] | str, notes: str = "") -> TagEntry:
        entry = TagEntry(normalise_tags(tags), notes.rstrip())
        if entry.empty:
            self._entries.pop(rel_path, None)
        else:
            self._entries[rel_path] = entry
        self.save()
        return entry

    def tags_by_path(self) -> dict[str, list[str]]:
        """Every tagged path and its tags (copies: editing them changes nothing)."""
        return {rel: list(e.tags) for rel, e in self._entries.items() if e.tags}

    def all_tags(self) -> list[str]:
        return [c.tag for c in count_tags(self.tags_by_path())]

    def paths_with_tag(self, tag: str) -> set[str]:
        return paths_with_tags(self.tags_by_path(), [tag])
