"""The library as a service for the shell, the CLI and plugins."""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

from staffroom.core import paths
from staffroom.core.library.db import LibraryDB
from staffroom.core.library.exclude import ExclusionList, ignore_file_path, read_ignore_file
from staffroom.core.library.index import Indexer, Progress
from staffroom.core.library.model import IndexStats, Kind, LibraryCounts, Resource, SearchHit
from staffroom.core.library.tags import (
    TagCount,
    TagEntry,
    TagStore,
    count_tags,
    normalise_tags,
    paths_with_tags,
)
from staffroom.core.log import get_logger

log = get_logger(__name__)

Opener = Callable[[Sequence[str]], None]
ExtFilter = str | tuple[str, ...] | None
"""A picker's filter: one extension like ``".py"``, several, or None for any."""
Picker = Callable[[ExtFilter], Path | None]

DEFAULT_RESOURCES_ROOT = ""


class ResourceService(Protocol):
    """What a plugin may ask the library for."""

    root: Path

    def pick(self, filter: ExtFilter = None) -> Path | None: ...
    def search(self, query: str) -> list[SearchHit]: ...
    def open_externally(self, path: Path) -> None: ...
    def open_for_class(self, path: Path, label: str) -> Path: ...


def library_db_path() -> Path:
    return paths.home_dir() / "library.db"


def _default_opener(args: Sequence[str]) -> None:
    subprocess.Popen(["open", *args])


def _normalise_root(root: Path) -> tuple[bool, Path]:
    """``(root_set, root)``. The config stores the folder as a string, and an
    empty string becomes ``Path("")``, which pathlib spells ``.``: resolving
    that would silently make the working directory the resources folder. An
    unset root stays unset; a set one is expanded and, when present, resolved."""
    if root == Path(""):
        return False, root
    expanded = root.expanduser()
    return True, expanded.resolve() if expanded.exists() else expanded


class LibraryService:
    """Owns the root, the database and the tag sidecar.

    ``opener`` runs macOS ``open`` by default; tests inject a recorder.
    ``picker`` is supplied by the shell (a dialog) or left None for the CLI.
    ``exclude`` is the configured exclusion list; the root's own
    ``.staffroom/ignore`` file is added to it whenever it is consulted.
    """

    root_set: bool  # False until a folder is chosen (config ``resources_root`` empty)

    def __init__(
        self,
        root: Path,
        db_path: Path | str | None = None,
        *,
        opener: Opener = _default_opener,
        picker: Picker | None = None,
        exclude: Sequence[str] = (),
    ) -> None:
        self.root_set, self.root = _normalise_root(root)
        self.db = LibraryDB(db_path if db_path is not None else library_db_path())
        if self.db.problem is not None:
            # The one log line (#65); the sidebar and ``staff library status``
            # repeat ``unavailable_reason`` but never log it again.
            log.warning("%s (%s); %s", self.db.problem, self.db.reason, self._fallback_note())
        self.tags = TagStore(self.root)
        self._opener = opener
        self._picker = picker
        self.configured_exclude: list[str] = list(exclude)

    def close(self) -> None:
        self.db.close()

    def set_root(self, root: Path) -> None:
        """Point at a different folder. The next index run must be ``full``
        so entries from the old folder are dropped."""
        self.root_set, self.root = _normalise_root(root)
        self.tags = TagStore(self.root)

    # -- exclusions ------------------------------------------------------
    def set_exclude(self, patterns: Sequence[str]) -> None:
        """Replace the configured patterns. Run :meth:`index` afterwards so
        excluded entries are dropped and newly allowed files are added."""
        self.configured_exclude = list(patterns)

    def exclusions(self) -> ExclusionList:
        """Configured patterns plus whatever ``<root>/.staffroom/ignore`` says
        right now."""
        return ExclusionList.for_root(self.root, self.configured_exclude)

    def ignore_file_patterns(self) -> list[str]:
        return read_ignore_file(self.root)

    @property
    def ignore_file(self) -> Path:
        return ignore_file_path(self.root)

    # -- availability (#65) ----------------------------------------------
    @property
    def available(self) -> bool:
        """False when the database could not be opened for writing (a
        read-only config home): nothing can be indexed this session. Every
        tool still runs; only the library is affected."""
        return self.db.writable

    @property
    def unavailable_reason(self) -> str | None:
        """``Resource Library unavailable: cannot write <path>``, or None."""
        return self.db.problem

    @property
    def searchable(self) -> bool:
        """True unless the session runs on an empty stand-in database. A
        read-only home with an earlier index still searches that index."""
        return self.available or self.db.mode == "read-only"

    def unavailable_detail(self) -> str:
        """The longer explanation behind :attr:`unavailable_reason`, for a
        tooltip or the CLI: what still works and what to change."""
        if self.available:
            return ""
        return (
            f"Staffroom cannot write {self.db.path} ({self.db.reason}). "
            f"{self._fallback_note().capitalize()}. Every tool still works. "
            f"Make {Path(self.db.path).parent} writable, or set STAFFROOM_HOME to a folder "
            "you can write, then restart."
        )

    def _fallback_note(self) -> str:
        if self.db.mode == "read-only":
            return "search uses the last index, read-only, and re-indexing is off"
        return "search and indexing are off for this session"

    # -- index -----------------------------------------------------------
    @property
    def root_exists(self) -> bool:
        """True only for a chosen folder that is there. An unset root is never
        the working directory, so nothing is indexed before the teacher picks."""
        return self.root_set and self.root.is_dir()

    def index(self, *, full: bool = False, progress: Progress | None = None) -> IndexStats:
        """Raises ``PermissionError`` (with :attr:`unavailable_reason`) when
        the database cannot be written, ``FileNotFoundError`` without a root."""
        if self.db.problem is not None:
            raise PermissionError(self.db.problem)
        if not self.root_exists:
            msg = f"resources root does not exist: {self.root}"
            raise FileNotFoundError(msg)
        return Indexer(self.root, self.db, self.exclusions()).run(full=full, progress=progress)

    def counts(self) -> LibraryCounts:
        """The one definition of "how many files" (#30): a tally over
        :meth:`resources` with hidden included, so a freshly excluded folder
        leaves the counts the moment it leaves the listing. The sidebar
        footer, the Resources header, ``staff library status`` and the index
        summary all show these numbers; nothing else counts rows."""
        return LibraryCounts.tally(self.resources(include_hidden=True))

    def count(self) -> int:
        """``counts().indexed``: every listable file, hidden ones included."""
        return self.counts().indexed

    def withheld_count(self) -> int:
        """``counts().name_only``: files whose text was withheld because it
        looked like pupil details."""
        return self.counts().name_only

    def withheld_paths(self) -> list[str]:
        return self.db.withheld_paths()

    def last_indexed(self) -> str | None:
        return self.db.get_meta("last_indexed")

    def resources(
        self, *, include_hidden: bool = False, tags: Sequence[str] = ()
    ) -> list[Resource]:
        """Everything indexed, minus anything the current exclusion list rules
        out (so a freshly excluded folder vanishes before the re-index lands).
        ``tags`` keeps only the files carrying every one of them (#111)."""
        rows = self.db.all(include_hidden=include_hidden)
        excl = self.exclusions()
        if excl:
            rows = [r for r in rows if not excl.matches(r.rel_path)]
        if tags:
            allowed = paths_with_tags(self.tags.tags_by_path(), tags)
            rows = [r for r in rows if r.rel_path in allowed]
        return rows

    def get(self, rel_path: str) -> Resource | None:
        if self.exclusions().matches(rel_path):
            return None
        return self.db.get(rel_path)

    # -- search ----------------------------------------------------------
    def search(
        self,
        query: str,
        *,
        kinds: Sequence[Kind] | None = None,
        tag: str | None = None,
        tags: Sequence[str] = (),
        include_hidden: bool = False,
        limit: int = 200,
    ) -> list[SearchHit]:
        """Hits for ``query``, narrowed by kind and by tag: ``tag`` (the CLI's
        one ``--tag``) and ``tags`` (the Library's filter) together, every
        one of them required."""
        hits = self.db.search(query, kinds=kinds, include_hidden=include_hidden, limit=limit)
        excl = self.exclusions()
        if excl:
            hits = [h for h in hits if not excl.matches(h.resource.rel_path)]
        chosen = normalise_tags([*tags, *([tag] if tag else [])])
        if chosen:
            allowed = paths_with_tags(self.tags.tags_by_path(), chosen)
            hits = [h for h in hits if h.resource.rel_path in allowed]
        return hits

    # -- tags ------------------------------------------------------------
    def tag_entry(self, rel_path: str) -> TagEntry:
        return self.tags.get(rel_path)

    def set_tags(self, rel_path: str, tags: list[str] | str, notes: str = "") -> TagEntry:
        return self.tags.set_entry(rel_path, tags, notes)

    def tag_counts(self, *, include_hidden: bool = False) -> list[TagCount]:
        """The tags on the files the Library lists, with how many carry each,
        most-used first: what the tag filter offers."""
        listed = [r.rel_path for r in self.resources(include_hidden=include_hidden)]
        return count_tags(self.tags.tags_by_path(), listed)

    # -- opening ---------------------------------------------------------
    def absolute(self, rel_path: str) -> Path:
        return self.root / Path(rel_path)

    def open_externally(self, path: Path) -> None:
        """Hand the file to its native app. Never parses it."""
        self._opener([str(path)])

    def reveal(self, path: Path) -> None:
        self._opener(["-R", str(path)])

    def pick(self, filter: ExtFilter = None) -> Path | None:
        if self._picker is None:
            return None
        return self._picker(filter)

    def open_for_class(self, path: Path, label: str) -> Path:
        msg = "open_for_class arrives with the classroom tool (Phase 1b)"
        raise NotImplementedError(msg)
