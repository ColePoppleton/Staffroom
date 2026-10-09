"""One definition of "how many files": every place that reports a library
file count derives it from :meth:`LibraryService.counts`, so the sidebar,
the Resources header, ``staff library status`` and the index summary agree
(#30). The fixture root has every flavour the definition must handle:
ordinary files, hidden cruft, an excluded folder, a cloud placeholder and a
file indexed by name only.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import load_config
from staffroom.core.library.model import LibraryCounts, Resource
from staffroom.core.library.service import LibraryService

runner = CliRunner()


@pytest.fixture
def mixed_root(tmp_path: Path) -> Path:
    """# FAKE DATA: invented files, no names, no pupils. Expected tallies:
    8 indexed (3 plain + 3 hidden + 1 cloud-only + 1 name only), 5 shown;
    the excluded folder's two files are never indexed."""
    root = tmp_path / "Resources"
    (root / "Python" / "__pycache__").mkdir(parents=True)
    (root / "Pupil work").mkdir()
    (root / "Python" / "loops.py").write_text("while True:\n    pass\n")
    (root / "Python" / "notes.md").write_text("# Notes\n\nIteration.\n")
    (root / "readme.txt").write_text("Plain text.\n")
    # hidden cruft (3): a dot-file, a cache folder's content, a zip
    (root / "Python" / ".DS_Store").write_bytes(b"\x00")
    (root / "Python" / "__pycache__" / "loops.cpython-313.pyc").write_bytes(b"\x00")
    (root / "old.zip").write_bytes(b"PK")
    # an evicted iCloud file (1): only the placeholder is on disk
    (root / "Python" / ".evicted.py.icloud").write_bytes(b"bplist00")
    # a file that looks like it holds pupil details (1): indexed by name only
    (root / "Python" / "task_submission.py").write_text(
        "# Candidate number: 4021\n# UPN: A123456789012\nprint(1)\n"
    )
    # excluded (never indexed, never counted)
    (root / "Pupil work" / "a.py").write_text("print('a')\n")
    (root / "Pupil work" / "b.py").write_text("print('b')\n")
    return root


@pytest.fixture
def svc(mixed_root: Path, tmp_path: Path) -> LibraryService:
    service = LibraryService(mixed_root, tmp_path / "library.db", exclude=["Pupil work"])
    service.index()
    return service


def test_counts_tally_every_flavour(svc: LibraryService) -> None:
    counts = svc.counts()
    assert counts == LibraryCounts(indexed=8, hidden=3, cloud_only=1, name_only=1)
    assert counts.shown == 5
    assert counts.visible(show_hidden=False) == 5
    assert counts.visible(show_hidden=True) == 8
    # The numbers are the sizes of what the tree actually lists.
    assert len(svc.resources()) == counts.shown
    assert len(svc.resources(include_hidden=True)) == counts.indexed
    # The old pass-throughs are the same definition.
    assert svc.count() == counts.indexed
    assert svc.withheld_count() == counts.name_only


def test_index_summary_carries_the_same_counts(svc: LibraryService) -> None:
    stats = svc.index()
    assert stats.counts == svc.counts()
    summary = stats.summary()
    assert summary.startswith("8 files in the index (3 hidden, 1 cloud-only, 1 name only)")
    assert "8 unchanged" in summary
    # The name-only sentence is about *this run*: nothing was re-extracted, so
    # it is absent here and back after a full re-index.
    assert "pupil details" not in summary
    assert "pupil details" in svc.index(full=True).summary()


def test_status_line_is_the_one_string_the_shell_shows(svc: LibraryService) -> None:
    counts = svc.counts()
    assert counts.status_line(show_hidden=False) == "5 files (3 hidden)  ·  1 name only"
    assert counts.status_line(show_hidden=True) == "8 files (incl. 3 hidden)  ·  1 name only"
    assert LibraryCounts().status_line(show_hidden=False) == "Nothing indexed yet"
    assert LibraryCounts(indexed=1).status_line(show_hidden=False) == "1 file"
    assert LibraryCounts(indexed=2, hidden=0).status_line(show_hidden=True) == "2 files"
    assert counts.status_line(show_hidden=False, sep="\n") == "5 files (3 hidden)\n1 name only"
    assert counts.describe() == "8 indexed: 5 shown, 3 hidden, 1 cloud-only, 1 name only"


def test_pending_exclusion_changes_counts_and_listing_together(svc: LibraryService) -> None:
    """Excluding a folder hides it before the re-index lands; the counts
    must drop with the listing, not wait for the database."""
    before = svc.counts()
    svc.set_exclude(["Pupil work", "__pycache__"])
    after = svc.counts()
    assert after.indexed == before.indexed - 1 and after.hidden == before.hidden - 1
    assert after.shown == before.shown
    assert len(svc.resources(include_hidden=True)) == after.indexed
    svc.index()  # the database follows
    assert svc.counts() == after


def test_tally_is_a_pure_function_over_resources() -> None:
    def res(rel: str, **flags: bool) -> Resource:
        return Resource(rel_path=rel, name=rel, ext="", kind="other", size=0, mtime=0.0, **flags)

    rows = [
        res("a"),
        res(".b", hidden=True),
        res("c", cloud_only=True),
        res("d", text_withheld=True),
        res(".e", hidden=True, text_withheld=True),
    ]
    expected = LibraryCounts(indexed=5, hidden=2, cloud_only=1, name_only=2)
    assert LibraryCounts.tally(rows) == expected
    assert LibraryCounts.tally([]) == LibraryCounts()


def test_cli_status_prints_the_same_numbers(
    mixed_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = load_config()
    cfg.general.resources_root = str(mixed_root)
    cfg.general.library_exclude = ["Pupil work"]
    cfg.save()
    r = runner.invoke(app, ["library", "index"])
    assert r.exit_code == 0, r.output
    assert "8 files in the index (3 hidden, 1 cloud-only, 1 name only)" in r.output
    r = runner.invoke(app, ["library", "status"])
    assert r.exit_code == 0, r.output
    assert "files:       8 indexed: 5 shown, 3 hidden, 1 cloud-only, 1 name only" in r.output
    assert "name only:   1 file" in r.output
