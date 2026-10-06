"""SQLite storage with an FTS5 index over file names and extracted text."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Sequence
from pathlib import Path
from types import TracebackType
from typing import cast

from teaching_tools.core.library.model import Kind, Resource, SearchHit

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    rel_path   TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    ext        TEXT NOT NULL,
    kind       TEXT NOT NULL,
    size       INTEGER NOT NULL,
    mtime      REAL NOT NULL,
    cloud_only INTEGER NOT NULL DEFAULT 0,
    hidden     INTEGER NOT NULL DEFAULT 0,
    has_text   INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    rel_path UNINDEXED, name, text, tokenize = 'unicode61'
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""

_TOKEN = re.compile(r"[\w'-]+", re.UNICODE)


def fts_query(user_query: str) -> str:
    """Turn free text into a safe FTS5 expression: every token quoted and
    prefix-matched, all required. ``while loop`` -> ``"while"* "loop"*``."""
    tokens = [t.replace('"', "") for t in _TOKEN.findall(user_query)]
    tokens = [t for t in tokens if t]
    return " ".join(f'"{t}"*' for t in tokens)


class LibraryDB:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path) if path != ":memory:" else path
        if isinstance(self.path, Path):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        if isinstance(self.path, Path):
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.executescript(SCHEMA)
        self._depth = 0

    # -- transactions ----------------------------------------------------
    def begin(self) -> None:
        """Start a bulk transaction; nest-safe. One commit for a whole index
        run instead of one fsync per file (the difference between 4 s and
        6 minutes on a 600-file folder)."""
        if self._depth == 0:
            self.conn.execute("BEGIN")
        self._depth += 1

    def commit(self) -> None:
        self._depth = max(0, self._depth - 1)
        if self._depth == 0 and self.conn.in_transaction:
            self.conn.execute("COMMIT")

    def _autocommit(self) -> bool:
        return self._depth == 0

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> LibraryDB:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- writes ----------------------------------------------------------
    def upsert(self, res: Resource, text: str | None) -> None:
        auto = self._autocommit()
        if auto:
            self.begin()
        try:
            self.conn.execute(
                """INSERT INTO files
                     (rel_path, name, ext, kind, size, mtime, cloud_only, hidden, has_text)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(rel_path) DO UPDATE SET
                     name=excluded.name, ext=excluded.ext, kind=excluded.kind,
                     size=excluded.size, mtime=excluded.mtime, cloud_only=excluded.cloud_only,
                     hidden=excluded.hidden, has_text=excluded.has_text""",
                (
                    res.rel_path,
                    res.name,
                    res.ext,
                    res.kind,
                    res.size,
                    res.mtime,
                    int(res.cloud_only),
                    int(res.hidden),
                    int(text is not None),
                ),
            )
            self.conn.execute("DELETE FROM fts WHERE rel_path = ?", (res.rel_path,))
            self.conn.execute(
                "INSERT INTO fts (rel_path, name, text) VALUES (?, ?, ?)",
                (res.rel_path, _searchable_name(res.name), text or ""),
            )
        finally:
            if auto:
                self.commit()

    def remove(self, rel_paths: Iterable[str]) -> int:
        paths = list(rel_paths)
        self.begin()
        try:
            for rel in paths:
                self.conn.execute("DELETE FROM files WHERE rel_path = ?", (rel,))
                self.conn.execute("DELETE FROM fts WHERE rel_path = ?", (rel,))
        finally:
            self.commit()
        return len(paths)

    def set_meta(self, key: str, value: str) -> None:
        self.begin()
        try:
            self.conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
        finally:
            self.commit()

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else cast(str, row["value"])

    # -- reads -----------------------------------------------------------
    def signatures(self) -> dict[str, tuple[float, int]]:
        """rel_path -> (mtime, size) for incremental indexing."""
        rows = self.conn.execute("SELECT rel_path, mtime, size FROM files").fetchall()
        return {r["rel_path"]: (r["mtime"], r["size"]) for r in rows}

    def count(self) -> int:
        return cast(int, self.conn.execute("SELECT COUNT(*) FROM files").fetchone()[0])

    def get(self, rel_path: str) -> Resource | None:
        row = self.conn.execute("SELECT * FROM files WHERE rel_path = ?", (rel_path,)).fetchone()
        return None if row is None else _to_resource(row)

    def all(self, *, include_hidden: bool = False) -> list[Resource]:
        sql = (
            "SELECT * FROM files"
            + ("" if include_hidden else " WHERE hidden = 0")
            + " ORDER BY rel_path"
        )
        return [_to_resource(r) for r in self.conn.execute(sql).fetchall()]

    def search(
        self,
        query: str,
        *,
        kinds: Sequence[Kind] | None = None,
        include_hidden: bool = False,
        limit: int = 200,
    ) -> list[SearchHit]:
        expr = fts_query(query)
        if not expr:
            return []
        sql = """
            SELECT f.*, snippet(fts, 2, '[', ']', '…', 14) AS snip, bm25(fts, 3.0, 1.0) AS score
            FROM fts JOIN files f ON f.rel_path = fts.rel_path
            WHERE fts MATCH ?
        """
        params: list[object] = [expr]
        if not include_hidden:
            sql += " AND f.hidden = 0"
        if kinds:
            sql += f" AND f.kind IN ({','.join('?' * len(kinds))})"
            params.extend(kinds)
        sql += " ORDER BY score LIMIT ?"
        params.append(limit)
        hits: list[SearchHit] = []
        for row in self.conn.execute(sql, params).fetchall():
            snippet = (row["snip"] or "").replace("\n", " ").strip()
            hits.append(SearchHit(_to_resource(row), snippet, float(row["score"])))
        return hits


def _searchable_name(name: str) -> str:
    """``while_loops-v2.py`` -> ``while_loops-v2.py while loops v2 py`` so
    tokens inside file names match."""
    words = re.split(r"[\W_]+", name)
    return name + " " + " ".join(w for w in words if w)


def _to_resource(row: sqlite3.Row) -> Resource:
    return Resource(
        rel_path=row["rel_path"],
        name=row["name"],
        ext=row["ext"],
        kind=cast(Kind, row["kind"]),
        size=row["size"],
        mtime=row["mtime"],
        cloud_only=bool(row["cloud_only"]),
        hidden=bool(row["hidden"]),
    )
