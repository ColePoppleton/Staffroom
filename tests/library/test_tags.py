import os
from pathlib import Path

from teaching_tools.core.library.service import LibraryService
from teaching_tools.core.library.tags import TagStore, normalise_tags


def test_normalise() -> None:
    assert normalise_tags(" Loops, KS3 ,loops,, ") == ["loops", "ks3"]


def test_tags_persist_and_resource_untouched(service: LibraryService, resources_root: Path) -> None:
    target = resources_root / "Python" / "Python_Course" / "while_loops.py"
    before = target.stat().st_mtime_ns
    service.set_tags("Python/Python_Course/while_loops.py", "loops, ks3", "Good starter.")
    assert target.stat().st_mtime_ns == before
    assert target.read_text().startswith("count = 0")
    sidecar = resources_root / ".teaching-tools" / "tags.json"
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
    assert all(".teaching-tools" not in r.rel_path for r in service.resources())
    assert os.path.exists(service.tags.path)
