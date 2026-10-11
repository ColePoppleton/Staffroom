import errno
import os
from pathlib import Path

import pytest

from staffroom.core import atomic
from staffroom.core.library.service import LibraryService
from staffroom.core.library.tags import TagStore, normalise_tags


def test_normalise() -> None:
    assert normalise_tags(" Loops, KS3 ,loops,, ") == ["loops", "ks3"]


def test_tags_persist_and_resource_untouched(service: LibraryService, resources_root: Path) -> None:
    target = resources_root / "Python" / "Python_Course" / "while_loops.py"
    before = target.stat().st_mtime_ns
    service.set_tags("Python/Python_Course/while_loops.py", "loops, ks3", "Good starter.")
    assert target.stat().st_mtime_ns == before
    assert target.read_text().startswith("count = 0")
    sidecar = resources_root / ".staffroom" / "tags.json"
    assert sidecar.exists()

    # "Restart": a fresh store reads the sidecar back.
    again = TagStore(resources_root)
    entry = again.get("Python/Python_Course/while_loops.py")
    assert entry.tags == ["loops", "ks3"] and entry.notes == "Good starter."
    assert again.all_tags() == ["ks3", "loops"]
    assert again.paths_with_tag("KS3") == {"Python/Python_Course/while_loops.py"}

    # Clearing removes the entry; the sidecar stays valid JSON.
    service.set_tags("Python/Python_Course/while_loops.py", "", "")
    assert TagStore(resources_root).get("Python/Python_Course/while_loops.py").empty


def test_sidecar_is_hidden_from_index(service: LibraryService) -> None:
    service.set_tags("Python/notes.md", "x")
    service.index()
    assert all(".staffroom" not in r.rel_path for r in service.resources())
    assert os.path.exists(service.tags.path)


def test_legacy_sidecar_is_read_and_migrated_on_save(resources_root: Path) -> None:
    # Tags written by the app under its old name must survive the rename.
    legacy = resources_root / ".teaching-tools" / "tags.json"
    legacy.parent.mkdir()
    legacy.write_text(
        '{"version": 1, "entries": {"Python/notes.md": {"tags": ["loops"], "notes": "old"}}}'
    )
    store = TagStore(resources_root)
    assert store.get("Python/notes.md").tags == ["loops"]

    store.set_entry("Python/readme.txt", "text")
    assert (resources_root / ".staffroom" / "tags.json").exists()
    assert legacy.exists(), "the old sidecar is left for an older checkout"
    again = TagStore(resources_root)
    assert again.get("Python/notes.md").notes == "old"
    assert again.get("Python/readme.txt").tags == ["text"]


def test_a_failed_save_keeps_the_sidecar(
    resources_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#125: a disk that fills mid-save leaves tags.json whole and no temp file."""
    store = TagStore(resources_root)
    store.set_entry("Python/notes.md", "loops")
    before = store.path.read_bytes()

    def no_space(fd: int) -> None:
        raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))

    monkeypatch.setattr(atomic.os, "fsync", no_space)
    with pytest.raises(OSError):
        store.set_entry("Python/readme.txt", "text")
    assert store.path.read_bytes() == before
    assert sorted(p.name for p in store.path.parent.iterdir()) == ["tags.json"]
    assert TagStore(resources_root).get("Python/readme.txt").tags == []
