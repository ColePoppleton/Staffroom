"""Tags and notes per resource, kept in a sidecar JSON file inside the root:
``<root>/.staffroom/tags.json``. Resource files are never written. A sidecar
left by the app under its old name (``.teaching-tools``) is still read; the
next save writes the new location."""

from __future__ import annotations

import json
import os
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

    def all_tags(self) -> list[str]:
        counts: dict[str, int] = {}
        for e in self._entries.values():
            for t in e.tags:
                counts[t] = counts.get(t, 0) + 1
        return sorted(counts, key=lambda t: (-counts[t], t))

    def paths_with_tag(self, tag: str) -> set[str]:
        tag = tag.strip().lower()
        return {rel for rel, e in self._entries.items() if tag in e.tags}
