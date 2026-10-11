"""The Library's type filter narrows the listing as well as search (#122):
``LibraryService.resources(kinds=...)`` keeps only those kinds, combines
with ``tags=`` and the *Hidden* toggle, and :class:`LibraryFilter` words
what the narrowed tree shows (``3 Python files tagged loops``).

The fixture root is invented: every file is marked ``# FAKE DATA`` and holds
no names. Nothing under it is written."""

from __future__ import annotations

from pathlib import Path

import pytest

from staffroom.core.library.filters import KIND_LABELS, LibraryFilter
from staffroom.core.library.model import KIND_BY_EXT
from staffroom.core.library.service import LibraryService

FILES = {
    "Python/Year 9/average.py": "# FAKE DATA\nscores = [4, 7]\nfor s in scores:\n    print(s)\n",
    "Python/Year 10/temperature.py": "# FAKE DATA\nwhile True:\n    break\n",
    "Python/Year 10/loops_notes.md": "# FAKE DATA\n\nFor and while loops.\n",
    "Theory/binary_recap.md": "# FAKE DATA\n\nBinary place value.\n",
    "Theory/hex_practice.txt": "# FAKE DATA\nHex practice: 0x1F.\n",
    "Theory/__pycache__/cached.py": "# FAKE DATA\nprint(1)\n",
}
TAGS = {
    "Python/Year 9/average.py": "loops, ks3",
    "Python/Year 10/temperature.py": "loops",
    "Python/Year 10/loops_notes.md": "loops",
    "Theory/binary_recap.md": "ks3",
}


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "FakeResources"
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def svc(root: Path, tmp_path: Path) -> LibraryService:
    service = LibraryService(root, tmp_path / "library.db", opener=lambda _a: None)
    service.index()
    for rel, tags in TAGS.items():
        service.set_tags(rel, tags)
    return service


def rels(service: LibraryService, **kwargs: object) -> set[str]:
    return {r.rel_path for r in service.resources(**kwargs)}  # type: ignore[arg-type]


# -- LibraryService.resources(kinds=...) ---------------------------------------
def test_kinds_narrow_the_listing(svc: LibraryService) -> None:
    assert rels(svc, kinds=["python"]) == {
        "Python/Year 9/average.py",
        "Python/Year 10/temperature.py",
    }
    assert rels(svc, kinds=["markdown", "text"]) == {
        "Python/Year 10/loops_notes.md",
        "Theory/binary_recap.md",
        "Theory/hex_practice.txt",
    }
    assert rels(svc, kinds=["pdf"]) == set()


def test_no_kinds_is_everything(svc: LibraryService) -> None:
    assert rels(svc, kinds=None) == rels(svc) == rels(svc, kinds=[])
    assert len(rels(svc)) == len(FILES) - 1  # the __pycache__ file is hidden


def test_kinds_combine_with_tags_and_hidden(svc: LibraryService) -> None:
    assert rels(svc, kinds=["python"], tags=["loops"]) == {
        "Python/Year 9/average.py",
        "Python/Year 10/temperature.py",
    }
    assert rels(svc, kinds=["python"], tags=["ks3"]) == {"Python/Year 9/average.py"}
    assert rels(svc, kinds=["markdown"], tags=["loops"]) == {"Python/Year 10/loops_notes.md"}
    assert rels(svc, kinds=["text"], tags=["loops"]) == set()
    assert "Theory/__pycache__/cached.py" in rels(svc, kinds=["python"], include_hidden=True)
    assert "Theory/__pycache__/cached.py" not in rels(svc, kinds=["python"])


def test_counts_stay_the_librarys_own(svc: LibraryService) -> None:
    """#30: the narrowing is the tree's alone; the one tally is unchanged."""
    before = svc.counts()
    svc.resources(kinds=["python"], tags=["loops"])
    assert svc.counts() == before
    assert before.shown == len(FILES) - 1


def test_the_resources_folder_is_not_written(svc: LibraryService, root: Path) -> None:
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    svc.resources(kinds=["python"], tags=["loops"])
    svc.resources(kinds=["text"])
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


# -- LibraryFilter -------------------------------------------------------------
def test_filter_off_by_default() -> None:
    view = LibraryFilter()
    assert not view.active
    assert view.kinds is None
    assert view.tags == ()


def test_filter_kinds() -> None:
    assert LibraryFilter(kind="python").kinds == ["python"]
    assert LibraryFilter(kind="all", tags=("loops",)).kinds is None
    assert LibraryFilter(kind="python").active
    assert LibraryFilter(tags=("loops",)).active


def test_filter_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError):
        LibraryFilter(kind="spreadsheet")


@pytest.mark.parametrize(
    ("view", "n", "line"),
    [
        (LibraryFilter(kind="python", tags=("loops",)), 3, "3 Python files tagged loops"),
        (LibraryFilter(kind="python"), 1, "1 Python file"),
        (LibraryFilter(kind="pdf"), 0, "0 PDF files"),
        (LibraryFilter(kind="csv"), 2, "2 CSV files"),
        (LibraryFilter(kind="text"), 2, "2 text files"),
        (LibraryFilter(kind="other"), 4, "4 other files"),
        (LibraryFilter(tags=("loops",)), 2, "2 files tagged loops"),
        (LibraryFilter(tags=("loops", "gcse")), 1, "1 file tagged loops + gcse"),
        (
            LibraryFilter(kind="markdown", tags=("ks3", "gcse")),
            0,
            "0 Markdown files tagged ks3 + gcse",
        ),
    ],
)
def test_filter_describes_what_the_tree_shows(view: LibraryFilter, n: int, line: str) -> None:
    assert view.describe(n) == line


def test_every_kind_has_a_label() -> None:
    assert set(KIND_LABELS) == {*KIND_BY_EXT.values(), "other"}
