"""Data types and classification rules for library entries."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
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
    #: Text deliberately left out of the index because it looked like pupil
    #: details (see :func:`staffroom.core.privacy.find_identifier_text`).
    text_withheld: bool = False

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


@dataclass(frozen=True)
class LibraryCounts:
    """How many files the library holds, by one definition (#30).

    ``indexed`` is every file in the index that the current exclusion list
    allows: the excluded are never counted, and hidden cruft, cloud
    placeholders and name-only files *are* counted, then reported as
    subsets so nothing is subtracted silently. ``shown`` is what the tree
    lists with *Hidden* off. Every count a teacher sees comes from
    :meth:`staffroom.core.library.service.LibraryService.counts`, which is
    :meth:`tally` over the listable resources; documented in
    ``docs/guide/launcher.md``.
    """

    indexed: int = 0
    hidden: int = 0
    cloud_only: int = 0
    name_only: int = 0

    @classmethod
    def tally(cls, resources: Iterable[Resource]) -> LibraryCounts:
        indexed = hidden = cloud = name_only = 0
        for r in resources:
            indexed += 1
            hidden += r.hidden
            cloud += r.cloud_only
            name_only += r.text_withheld
        return cls(indexed=indexed, hidden=hidden, cloud_only=cloud, name_only=name_only)

    @property
    def shown(self) -> int:
        """Files listed with *Hidden* off."""
        return self.indexed - self.hidden

    def visible(self, *, show_hidden: bool) -> int:
        """Files listed with the *Hidden* toggle in the given state."""
        return self.indexed if show_hidden else self.shown

    def status_line(self, *, show_hidden: bool, sep: str = "  ·  ") -> str:
        """The terse line the sidebar footer and the Resources header both
        start with: ``563 files (24 hidden)  ·  3 name only``. The narrow
        sidebar passes ``sep="\\n"`` so the tail is not clipped."""
        if self.indexed == 0:
            return "Nothing indexed yet"
        n = self.visible(show_hidden=show_hidden)
        line = f"{n} file{'s' if n != 1 else ''}"
        if self.hidden:
            line += f" (incl. {self.hidden} hidden)" if show_hidden else f" ({self.hidden} hidden)"
        if self.name_only:
            line += f"{sep}{self.name_only} name only"
        return line

    def describe(self) -> str:
        """The long form for ``staff library status`` and the index summary:
        ``587 indexed: 563 shown, 24 hidden, 2 cloud-only, 3 name only``."""
        return (
            f"{self.indexed} indexed: {self.shown} shown, {self.hidden} hidden, "
            f"{self.cloud_only} cloud-only, {self.name_only} name only"
        )

    def parenthetical(self) -> str:
        """``(24 hidden, 2 cloud-only, 3 name only)`` after a file count."""
        return f"({self.hidden} hidden, {self.cloud_only} cloud-only, {self.name_only} name only)"


@dataclass
class IndexStats:
    scanned: int = 0
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    removed: int = 0
    cloud_only: int = 0
    text_indexed: int = 0
    #: Files whose text was left out because it looked like pupil details.
    text_withheld: int = 0
    withheld_paths: list[str] = field(default_factory=list)
    excluded: int = 0  #: patterns in force during this run
    seconds: float = 0.0
    #: What the index holds after this run, by the one definition
    #: (:class:`LibraryCounts`); the same numbers the sidebar and header show.
    counts: LibraryCounts = field(default_factory=LibraryCounts)

    def summary(self) -> str:
        line = (
            f"{self.counts.indexed} files in the index {self.counts.parenthetical()}: "
            f"{self.added} added, {self.updated} updated, {self.unchanged} unchanged, "
            f"{self.removed} removed; {self.text_indexed} with text; {self.seconds:.1f}s"
        )
        if self.text_withheld:
            line += "\n" + withheld_message(self.text_withheld)
        return line


def withheld_message(count: int) -> str:
    """The sentence shown wherever a count of name-only files is reported."""
    files = "file" if count == 1 else "files"
    return (
        f"{count} {files} skipped for text: they look like they hold pupil details "
        "(candidate number, surname, UPN, date of birth near a value). Only the file "
        "name was indexed. Exclude the folder or keep them out of the resources root."
    )
