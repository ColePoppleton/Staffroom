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
from staffroom.core.library.model import IndexStats, Kind, Resource, SearchHit
from staffroom.core.library.tags import TagEntry, TagStore

Opener = Callable[[Sequence[str]], None]
Picker = Callable[[str | None], Path | None]

DEFAULT_RESOURCES_ROOT = ""


class ResourceService(Protocol):
    """What a plugin may ask the library for."""

    root: Path

    def pick(self, filter: str | None = None) -> Path | None: ...
    def search(self, query: str) -> list[SearchHit]: ...
    def open_externally(self, path: Path) -> None: ...
    def open_for_class(self, path: Path, label: str) -> Path: ...


def library_db_path() -> Path:
    return paths.home_dir() / "library.db"


def _default_opener(args: Sequence[str]) -> None:
    subprocess.Popen(["open", *args])


class LibraryService:
    """Owns the root, the database and the tag sidecar.

    ``opener`` runs macOS ``open`` by default; tests inject a recorder.
    ``picker`` is supplied by the shell (a dialog) or left None for the CLI.
    ``exclude`` is the configured exclusion list; the root's own
    ``.staffroom/ignore`` file is added to it whenever it is consulted.
    """

    def __init__(
        self,
        root: Path,
        db_path: Path | str | None = None,
        *,
        opener: Opener = _default_opener,
        picker: Picker | None = None,
        exclude: Sequence[str] = (),
    ) -> None:
        self.root = root.expanduser().resolve() if root.expanduser().exists() else root.expanduser()
        self.db = LibraryDB(db_path if db_path is not None else library_db_path())
        self.tags = TagStore(self.root)
        self._opener = opener
        self._picker = picker
        self.configured_exclude: list[str] = list(exclude)

    def close(self) -> None:
        self.db.close()

    def set_root(self, root: Path) -> None:
        """Point at a different folder. The next index run must be ``full``
        so entries from the old folder are dropped."""
        self.root = root.expanduser().resolve() if root.expanduser().exists() else root.expanduser()
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

    # -- index -----------------------------------------------------------
    @property
    def root_exists(self) -> bool:
        return self.root.is_dir()

    def index(self, *, full: bool = False, progress: Progress | None = None) -> IndexStats:
        if not self.root_exists:
            msg = f"resources root does not exist: {self.root}"
            raise FileNotFoundError(msg)
        return Indexer(self.root, self.db, self.exclusions()).run(full=full, progress=progress)

    def count(self) -> int:
        return self.db.count()

    def withheld_count(self) -> int:
        """Indexed files whose text was withheld because it looked like pupil
        details. Shown in the sidebar status and ``staff library status``."""
        return self.db.withheld_count()

    def withheld_paths(self) -> list[str]:
        return self.db.withheld_paths()

    def last_indexed(self) -> str | None:
        return self.db.get_meta("last_indexed")

    def resources(self, *, include_hidden: bool = False) -> list[Resource]:
        """Everything indexed, minus anything the current exclusion list rules
        out (so a freshly excluded folder vanishes before the re-index lands)."""
        rows = self.db.all(include_hidden=include_hidden)
        excl = self.exclusions()
        return [r for r in rows if not excl.matches(r.rel_path)] if excl else rows

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
        include_hidden: bool = False,
        limit: int = 200,
    ) -> list[SearchHit]:
        hits = self.db.search(query, kinds=kinds, include_hidden=include_hidden, limit=limit)
        excl = self.exclusions()
        if excl:
            hits = [h for h in hits if not excl.matches(h.resource.rel_path)]
        if tag:
            allowed = self.tags.paths_with_tag(tag)
            hits = [h for h in hits if h.resource.rel_path in allowed]
        return hits

    # -- tags ------------------------------------------------------------
    def tag_entry(self, rel_path: str) -> TagEntry:
        return self.tags.get(rel_path)

    def set_tags(self, rel_path: str, tags: list[str] | str, notes: str = "") -> TagEntry:
        return self.tags.set_entry(rel_path, tags, notes)

    # -- opening ---------------------------------------------------------
    def absolute(self, rel_path: str) -> Path:
        return self.root / Path(rel_path)

    def open_externally(self, path: Path) -> None:
        """Hand the file to its native app. Never parses it."""
        self._opener([str(path)])

    def reveal(self, path: Path) -> None:
        self._opener(["-R", str(path)])

    def pick(self, filter: str | None = None) -> Path | None:
        if self._picker is None:
            return None
        return self._picker(filter)

    def open_for_class(self, path: Path, label: str) -> Path:
        msg = "open_for_class arrives with the classroom tool (Phase 1b)"
        raise NotImplementedError(msg)
