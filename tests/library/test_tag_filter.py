"""Filtering the library by tag (#111): the tags in use with their counts,
and the files carrying every chosen tag, for the tree and for search.

The fixture root is invented: every file is marked ``# FAKE DATA`` and holds
no names. Tags live only in ``<root>/.staffroom/tags.json``; the files are
never written."""

from __future__ import annotations

from pathlib import Path

import pytest

from staffroom.core.library.service import LibraryService
from staffroom.core.library.tags import TagCount, TagStore, count_tags, paths_with_tags

FILES = {
    "Python/Year 9/average.py": "# FAKE DATA\nscores = [4, 7]\nfor s in scores:\n    print(s)\n",
    "Python/Year 10/temperature.py": "# FAKE DATA\nwhile True:\n    break\n",
    "Python/Year 10/search.py": "# FAKE DATA\nitems = [3, 1]\nprint(3 in items)\n",
    "Theory/binary_recap.md": "# FAKE DATA\n\nBinary and loops of place value.\n",
    "Theory/hex_practice.txt": "# FAKE DATA\nHex practice: 0x1F.\n",
}

TAGS = {
    "Python/Year 9/average.py": "loops, ks3, lists",
    "Python/Year 10/temperature.py": "loops, gcse",
    "Theory/binary_recap.md": "ks3, gcse",
    "Theory/hex_practice.txt": "gcse",
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


# -- the pure helpers ----------------------------------------------------------
def test_count_tags_most_used_first_then_by_name() -> None:
    tags = {"a.py": ["loops", "ks3"], "b.py": ["loops"], "c.md": ["gcse", "ks3"], "d.txt": []}
    assert count_tags(tags) == [
        TagCount("ks3", 2),
        TagCount("loops", 2),
        TagCount("gcse", 1),
    ]


def test_count_tags_only_counts_the_paths_listed() -> None:
    """A sidecar entry for a file that is gone, excluded or hidden is not a
    file the teacher can reach, so it does not count."""
    tags = {"a.py": ["loops"], "gone.py": ["loops", "old"]}
    assert count_tags(tags, within=["a.py", "b.py"]) == [TagCount("loops", 1)]


def test_paths_with_tags_needs_every_chosen_tag() -> None:
    tags = {"a.py": ["loops", "ks3"], "b.py": ["loops"], "c.md": ["ks3"]}
    assert paths_with_tags(tags, ["loops"]) == {"a.py", "b.py"}
    assert paths_with_tags(tags, ["Loops ", "KS3"]) == {"a.py"}  # normalised like the sidecar
    assert paths_with_tags(tags, ["missing"]) == set()


def test_tag_count_label() -> None:
    assert TagCount("loops", 3).label == "loops  3"


# -- the store and the service -------------------------------------------------
def test_store_lists_tags_by_path_as_copies(svc: LibraryService) -> None:
    by_path = svc.tags.tags_by_path()
    assert by_path["Theory/hex_practice.txt"] == ["gcse"]
    by_path["Theory/hex_practice.txt"].append("changed")
    assert svc.tags.get("Theory/hex_practice.txt").tags == ["gcse"]


def test_tag_counts_over_the_listed_files(svc: LibraryService, root: Path) -> None:
    assert svc.tag_counts() == [
        TagCount("gcse", 3),
        TagCount("ks3", 2),
        TagCount("loops", 2),
        TagCount("lists", 1),
    ]
    # Excluding a folder drops its files' tags from the counts at once.
    svc.set_exclude(["Theory/"])
    assert svc.tag_counts() == [
        TagCount("loops", 2),
        TagCount("gcse", 1),
        TagCount("ks3", 1),
        TagCount("lists", 1),
    ]


def test_resources_narrowed_by_tags(svc: LibraryService) -> None:
    every = {r.rel_path for r in svc.resources()}
    assert {r.rel_path for r in svc.resources(tags=())} == every
    assert {r.rel_path for r in svc.resources(tags=["loops"])} == {
        "Python/Year 9/average.py",
        "Python/Year 10/temperature.py",
    }
    assert {r.rel_path for r in svc.resources(tags=["loops", "gcse"])} == {
        "Python/Year 10/temperature.py"
    }
    assert svc.resources(tags=["nothing-has-this"]) == []


def test_search_combines_query_kind_and_tags(svc: LibraryService) -> None:
    def found(**kw: object) -> set[str]:
        return {h.resource.rel_path for h in svc.search("FAKE", **kw)}  # type: ignore[arg-type]

    assert len(found()) == len(FILES)
    assert found(tags=["gcse"]) == {
        "Python/Year 10/temperature.py",
        "Theory/binary_recap.md",
        "Theory/hex_practice.txt",
    }
    assert found(tags=["gcse"], kinds=["python"]) == {"Python/Year 10/temperature.py"}
    assert found(tags=["gcse", "ks3"]) == {"Theory/binary_recap.md"}
    # The CLI's single --tag still works, and adds to the list.
    assert found(tag="ks3") == {"Python/Year 9/average.py", "Theory/binary_recap.md"}
    assert found(tag="ks3", tags=["lists"]) == {"Python/Year 9/average.py"}


def test_filtering_never_writes_the_resources_folder(svc: LibraryService, root: Path) -> None:
    before = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    svc.tag_counts()
    svc.resources(tags=["loops"])
    svc.search("FAKE", tags=["ks3"])
    after = {p: p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()}
    assert after == before
    # The only thing Staffroom ever writes there is its own sidecar.
    assert {p.relative_to(root).as_posix() for p in after} - set(FILES) == {".staffroom/tags.json"}
    assert TagStore(root).paths_with_tag("gcse") == {
        "Python/Year 10/temperature.py",
        "Theory/binary_recap.md",
        "Theory/hex_practice.txt",
    }
