"""The exclusion list: patterns from config and from ``<root>/.staffroom/ignore``
keep folders out of the scan, the listing and the search; changing the list
and re-indexing drops what is now excluded. Fixtures are invented and hold
no names."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from staffroom.core.library.db import LibraryDB
from staffroom.core.library.exclude import (
    ExclusionList,
    normalise_patterns,
    read_ignore_file,
)
from staffroom.core.library.scan import scan
from staffroom.core.library.service import LibraryService


def test_normalise_patterns() -> None:
    raw = ["  Pupil work ", "", "# a comment", "./Year 11/Mocks/", "*.bak", "Pupil work", "a\\b"]
    assert normalise_patterns(raw) == ["Pupil work", "Year 11/Mocks", "*.bak", "a/b"]


def test_name_patterns_match_any_depth_case_insensitively() -> None:
    excl = ExclusionList(["Pupil work", "*.bak", "*assessment*"])
    assert excl.matches("Pupil work")
    assert excl.matches("Year 9/pupil WORK/task.py")
    assert excl.matches("Python/old.BAK")
    assert excl.matches("GCSE/Mock Assessment 2/paper.pdf")
    assert not excl.matches("Python/while_loops.py")
    assert not excl.matches("")
    assert len(excl) == 3 and bool(excl)
    assert not ExclusionList()


def test_path_patterns_match_from_the_root() -> None:
    excl = ExclusionList(["Year 11/Mocks", "*/submissions/"])
    assert excl.matches("Year 11/Mocks")
    assert excl.matches("Year 11/Mocks/paper_1.pdf")
    assert not excl.matches("Archive/Year 11/Mocks/paper_1.pdf")
    assert excl.matches("Year 8/submissions/task.py")
    assert not excl.matches("Year 8/deep/submissions/task.py")  # one segment only
    assert not excl.matches("Year 11/Mock schemes/scheme.md")


def test_ignore_file_is_read_from_sidecar_and_legacy(tmp_path: Path) -> None:
    root = tmp_path / "Resources"
    root.mkdir()
    assert read_ignore_file(root) == []
    legacy = root / ".teaching-tools" / "ignore"
    legacy.parent.mkdir()
    legacy.write_text("Legacy folder\n")
    assert read_ignore_file(root) == ["Legacy folder"]
    current = root / ".staffroom" / "ignore"
    current.parent.mkdir()
    current.write_text("# folders that hold pupil work\nPupil work/\n\n*.bak\n")
    assert read_ignore_file(root) == ["Pupil work", "*.bak"]
    assert ExclusionList.for_root(root, ["Extra"]).patterns == ["Extra", "Pupil work", "*.bak"]


def test_scan_prunes_excluded_folders(resources_root: Path) -> None:
    excl = ExclusionList(["OCR Booklet", "*.csv"])
    rels = {r.rel_path for r in scan(resources_root, excl.matches)}
    assert "Python/Python_Course/while_loops.py" in rels
    assert not any(r.startswith("Python/OCR Booklet/") for r in rels)
    assert "Python/marks.csv" not in rels
    everything = {r.rel_path for r in scan(resources_root)}
    assert "Python/OCR Booklet/booklet.pdf" in everything


def _service(root: Path, tmp_path: Path, exclude: list[str]) -> LibraryService:
    return LibraryService(root, tmp_path / "library.db", opener=lambda a: None, exclude=exclude)


def test_excluded_paths_are_neither_indexed_nor_listed(
    resources_root: Path, tmp_path: Path
) -> None:
    svc = _service(resources_root, tmp_path, ["OCR Booklet"])
    stats = svc.index()
    assert stats.excluded == 1
    listed = {r.rel_path for r in svc.resources(include_hidden=True)}
    assert listed and not any("OCR Booklet" in r for r in listed)
    assert svc.get("Python/OCR Booklet/exercise_3a.py") is None
    assert all("OCR Booklet" not in h.resource.rel_path for h in svc.search("while"))


def test_changing_the_list_and_reindexing_drops_and_restores(
    resources_root: Path, tmp_path: Path
) -> None:
    svc = _service(resources_root, tmp_path, [])
    svc.index()
    assert svc.get("Python/OCR Booklet/exercise_3a.py") is not None
    before = svc.count()

    svc.set_exclude(["OCR Booklet"])
    # Listing and lookup hide it straight away...
    assert svc.get("Python/OCR Booklet/exercise_3a.py") is None
    assert all("OCR Booklet" not in r.rel_path for r in svc.resources())
    # ...and the incremental re-index removes the rows.
    stats = svc.index()
    assert stats.removed == 3  # exercise_3a.py, booklet.doc, booklet.pdf
    assert svc.count() == before - 3
    assert svc.db.get("Python/OCR Booklet/exercise_3a.py") is None

    svc.set_exclude([])
    stats = svc.index()
    assert stats.added == 3 and svc.count() == before


def test_ignore_file_in_root_is_honoured_without_config(
    resources_root: Path, tmp_path: Path
) -> None:
    (resources_root / ".staffroom").mkdir()
    (resources_root / ".staffroom" / "ignore").write_text("Scratch\n")
    svc = _service(resources_root, tmp_path, [])
    svc.index()
    assert svc.ignore_file_patterns() == ["Scratch"]
    assert not any(r.rel_path.startswith("Scratch/") for r in svc.resources())
    # The app never writes the ignore file; the resources root stays read-only.
    assert (resources_root / ".staffroom" / "ignore").read_text() == "Scratch\n"


def test_full_reindex_after_root_change_drops_old_entries(
    resources_root: Path, tmp_path: Path
) -> None:
    svc = _service(resources_root, tmp_path, [])
    svc.index()
    old = {r.rel_path for r in svc.resources(include_hidden=True)}
    assert old
    other = tmp_path / "Other"
    other.mkdir()
    (other / "starter.py").write_text("print('hi')\n")
    svc.set_root(other)
    stats = svc.index(full=True)
    assert stats.removed == len(old)
    assert {r.rel_path for r in svc.resources(include_hidden=True)} == {"starter.py"}
    assert svc.search("while") == []
    assert svc.db.get_meta("root") == str(other.resolve())


def test_old_database_gains_the_withheld_column(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE files (
            rel_path TEXT PRIMARY KEY, name TEXT NOT NULL, ext TEXT NOT NULL,
            kind TEXT NOT NULL, size INTEGER NOT NULL, mtime REAL NOT NULL,
            cloud_only INTEGER NOT NULL DEFAULT 0, hidden INTEGER NOT NULL DEFAULT 0,
            has_text INTEGER NOT NULL DEFAULT 0
        );
        INSERT INTO files VALUES ('a.py', 'a.py', '.py', 'python', 1, 1.0, 0, 0, 1);
        """
    )
    conn.commit()
    conn.close()
    db = LibraryDB(path)
    res = db.get("a.py")
    assert res is not None and res.text_withheld is False
    assert db.withheld_count() == 0
    db.close()
