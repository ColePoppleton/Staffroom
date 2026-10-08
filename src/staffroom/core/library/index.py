"""Incremental indexer: scan the root, (re)extract text for new or changed
files, drop entries whose files have gone."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from staffroom.core.library.db import LibraryDB
from staffroom.core.library.extract import CloudOnlyError, extract_text
from staffroom.core.library.model import IndexStats, Resource
from staffroom.core.library.scan import scan
from staffroom.core.log import get_logger

log = get_logger(__name__)

Progress = Callable[[int, int, str], None]  # done, total, current rel_path


class Indexer:
    def __init__(self, root: Path, db: LibraryDB) -> None:
        self.root = root
        self.db = db

    def run(self, *, full: bool = False, progress: Progress | None = None) -> IndexStats:
        started = time.perf_counter()
        stats = IndexStats()
        known = {} if full else self.db.signatures()
        seen: set[str] = set()
        found = list(scan(self.root))
        total = len(found)
        self.db.begin()
        try:
            self._process(found, known, seen, stats, progress)
        finally:
            self.db.commit()
        stale = [rel for rel in self.db.signatures() if rel not in seen]
        stats.removed = self.db.remove(stale)
        stats.seconds = time.perf_counter() - started
        self.db.set_meta("last_indexed", datetime.now(UTC).isoformat(timespec="seconds"))
        self.db.set_meta("root", str(self.root))
        if progress:
            progress(total, total, "")
        log.info("indexed %s: %s", self.root, stats.summary())
        return stats

    def _process(
        self,
        found: list[Resource],
        known: dict[str, tuple[float, int]],
        seen: set[str],
        stats: IndexStats,
        progress: Progress | None,
    ) -> None:
        total = len(found)
        for i, res in enumerate(found):
            seen.add(res.rel_path)
            stats.scanned += 1
            if progress:
                progress(i, total, res.rel_path)
            sig = known.get(res.rel_path)
            if sig is not None and sig == (res.mtime, res.size):
                stats.unchanged += 1
                continue
            res, text = self._extract(res)
            self.db.upsert(res, text)
            if res.cloud_only:
                stats.cloud_only += 1
            if text is not None:
                stats.text_indexed += 1
            if sig is None:
                stats.added += 1
            else:
                stats.updated += 1

    def _extract(self, res: Resource) -> tuple[Resource, str | None]:
        if res.cloud_only:
            return res, None
        try:
            return res, extract_text(res, self.root)
        except CloudOnlyError:
            log.info("cloud-only: %s", res.rel_path)
            return replace(res, cloud_only=True), None
        except OSError as exc:
            log.warning("could not read %s: %s", res.rel_path, exc)
            return res, None
