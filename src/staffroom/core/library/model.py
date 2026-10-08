"""Data types and classification rules for library entries."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Literal

Kind = Literal[
    "python",
    "text",
    "markdown",
    "csv",
    "pdf",
    "image",
    "office",
    "scratch",
    "audio",
    "video",
    "archive",
    "database",
    "diagram",
    "other",
]

KIND_BY_EXT: dict[str, Kind] = {
    ".py": "python",
    ".pyw": "python",
    ".txt": "text",
    ".md": "markdown",
    ".csv": "csv",
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".bmp": "image",
    ".svg": "image",
    ".webp": "image",
    ".doc": "office",
    ".docx": "office",
    ".ppt": "office",
    ".pptx": "office",
    ".pub": "office",
    ".xls": "office",
    ".xlsx": "office",
    ".odt": "office",
    ".odp": "office",
    ".key": "office",
    ".pages": "office",
    ".numbers": "office",
    ".sb": "scratch",
    ".sb2": "scratch",
    ".sb3": "scratch",
    ".wav": "audio",
    ".mp3": "audio",
    ".m4a": "audio",
    ".wmv": "video",
    ".mp4": "video",
    ".mov": "video",
    ".avi": "video",
    ".zip": "archive",
    ".tar": "archive",
    ".gz": "archive",
    ".7z": "archive",
    ".db": "database",
    ".sqlite": "database",
    ".sqlite3": "database",
    ".drawio": "diagram",
    ".fprg": "diagram",
}

#: Kinds whose text is extracted for search and preview. Nothing else is parsed.
SEARCHABLE_KINDS: frozenset[str] = frozenset({"python", "text", "markdown", "csv", "pdf"})

#: Kinds that are shown as a card and opened in their native app only.
EXTERNAL_ONLY_KINDS: frozenset[str] = frozenset(
    {"office", "scratch", "audio", "video", "archive", "database", "diagram", "other"}
)

HIDDEN_NAMES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})
HIDDEN_DIRS: frozenset[str] = frozenset(
    {"__pycache__", ".idea", ".git", ".staffroom", ".teaching-tools"}
)
HIDDEN_EXTS: frozenset[str] = frozenset({".zip"})

CLOUD_SUFFIX = ".icloud"


def kind_for(path: PurePath) -> Kind:
    return KIND_BY_EXT.get(path.suffix.lower(), "other")


def is_hidden(rel_path: PurePath) -> bool:
    """Cruft hidden by default: the listed names/dirs/extensions plus any
    dot-file or dot-directory. Toggle "show hidden" in the UI to see them."""
    parts = rel_path.parts
    if not parts:
        return False
    if any(p in HIDDEN_DIRS for p in parts[:-1]):
        return True
    name = parts[-1]
    if name in HIDDEN_NAMES or rel_path.suffix.lower() in HIDDEN_EXTS:
        return True
    return any(p.startswith(".") and not is_cloud_placeholder_name(p) for p in parts)


def is_cloud_placeholder_name(name: str) -> bool:
    """iCloud evicted files appear as ``.Original Name.ext.icloud``."""
    return (
        name.startswith(".") and name.endswith(CLOUD_SUFFIX) and len(name) > len(CLOUD_SUFFIX) + 1
    )


def real_name_from_placeholder(name: str) -> str:
    return name[1 : -len(CLOUD_SUFFIX)]


@dataclass(frozen=True)
class Resource:
    """One indexed file. ``rel_path`` is POSIX-style, relative to the root."""

    rel_path: str
    name: str
    ext: str
    kind: Kind
    size: int
    mtime: float
    cloud_only: bool = False
    hidden: bool = False

    def absolute(self, root: Path) -> Path:
        return root / Path(self.rel_path)

    @property
    def searchable(self) -> bool:
        return self.kind in SEARCHABLE_KINDS and not self.cloud_only

    @property
    def external_only(self) -> bool:
        return self.kind in EXTERNAL_ONLY_KINDS


@dataclass(frozen=True)
class SearchHit:
    resource: Resource
    snippet: str
    score: float


@dataclass
class IndexStats:
    scanned: int = 0
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    cloud_only: int = 0
    text_indexed: int = 0
    seconds: float = 0.0

    def summary(self) -> str:
        return (
            f"{self.scanned} files scanned: {self.added} added, {self.updated} updated, "
            f"{self.unchanged} unchanged, {self.removed} removed; {self.cloud_only} cloud-only; "
            f"{self.text_indexed} with text; {self.seconds:.1f}s"
        )
