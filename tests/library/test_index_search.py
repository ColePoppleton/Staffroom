import errno
import os
import time
from pathlib import Path

import pytest

from teaching_tools.core.library.db import fts_query
from teaching_tools.core.library.service import LibraryService


def test_fts_query_is_safe() -> None:
    assert fts_query("while loop") == '"while"* "loop"*'
    assert fts_query('a "b" OR (c)') == '"a"* "b"* "OR"* "c"*'
    assert fts_query("   ") == ""


def test_index_counts_and_hidden(service: LibraryService) -> None:
    visible = service.resources()
    everything = service.resources(include_hidden=True)
    assert len(everything) > len(visible)
    names = {r.name for r in visible}
    assert {"while_loops.py", "while_loops.pptx", "booklet.pdf", "cloud_file.py"} <= names
    assert "junk.cpython-313.pyc" not in names and ".DS_Store" not in names
    cloud = service.get("Python/cloud_file.py")
    assert cloud is not None and cloud.cloud_only


def test_search_while_finds_py_pdf_and_names(service: LibraryService) -> None:
    hits = service.search("while")
    paths = [h.resource.rel_path for h in hits]
    assert "Python/Python_Course/while_loops.py" in paths
    assert "Python/OCR Booklet/exercise_3a.py" in paths
    assert "Python/OCR Booklet/booklet.pdf" in paths
    assert "Python/Python_Course/while_loops.pptx" in paths  # by name only
    assert "Python/notes.md" in paths
    assert any("[while]" in h.snippet for h in hits)
    assert "Python/readme.txt" not in paths


def test_search_filters(service: LibraryService) -> None:
    only_pdf = service.search("while", kinds=["pdf"])
    assert {h.resource.kind for h in only_pdf} == {"pdf"}
    service.set_tags("Python/notes.md", "loops, ks3")
    tagged = service.search("while", tag="loops")
    assert [h.resource.rel_path for h in tagged] == ["Python/notes.md"]
    assert service.search("") == []


def test_incremental_index(service: LibraryService, resources_root: Path) -> None:
    stats = service.index()
    assert stats.added == 0 and stats.updated == 0 and stats.unchanged == stats.scanned
    new = resources_root / "Python" / "for_loops.py"
    new.write_text("for i in range(3): pass\n")
    changed = resources_root / "Python" / "readme.txt"
    time.sleep(0.01)
    changed.write_text("now mentions while\n")
    os.utime(changed, None)
    (resources_root / "Python" / "marks.csv").unlink()
    stats = service.index()
    assert stats.added == 1 and stats.updated == 1 and stats.removed == 1
    assert "Python/readme.txt" in [h.resource.rel_path for h in service.search("while")]
    assert service.get("Python/marks.csv") is None


def test_index_survives_deadlock_reads(
    service: LibraryService, resources_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    victim = resources_root / "Python" / "readme.txt"
    victim.write_text("changed so it is re-read")
    real_open = Path.open

    def boom(self: Path, *a: object, **k: object) -> object:
        if self == victim:
            raise OSError(errno.EDEADLK, "Resource deadlock avoided")
        return real_open(self, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", boom)
    stats = service.index()
    assert stats.cloud_only >= 1
    res = service.get("Python/readme.txt")
    assert res is not None and res.cloud_only


def test_missing_root(tmp_path: Path) -> None:
    svc = LibraryService(tmp_path / "nope", tmp_path / "db.sqlite")
    assert not svc.root_exists
    with pytest.raises(FileNotFoundError):
        svc.index()
    assert svc.count() == 0


def test_open_externally_never_reads(service: LibraryService, opened: list[list[str]]) -> None:
    p = service.absolute("Python/Python_Course/while_loops.pptx")
    service.open_externally(p)
    service.reveal(p)
    assert opened == [[str(p)], ["-R", str(p)]]
    with pytest.raises(NotImplementedError):
        service.open_for_class(p, "P3")
