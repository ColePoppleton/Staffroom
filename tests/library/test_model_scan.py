from pathlib import Path, PurePosixPath

from teaching_tools.core.library.model import is_hidden, kind_for
from teaching_tools.core.library.scan import scan


def test_kinds() -> None:
    assert kind_for(PurePosixPath("a.PY")) == "python"
    assert kind_for(PurePosixPath("a.pptx")) == "office"
    assert kind_for(PurePosixPath("a.sb")) == "scratch"
    assert kind_for(PurePosixPath("a.weird")) == "other"


def test_hidden_rules() -> None:
    assert is_hidden(PurePosixPath("Python/__pycache__/x.pyc"))
    assert is_hidden(PurePosixPath(".idea/workspace.xml"))
    assert is_hidden(PurePosixPath("Python/.DS_Store"))
    assert is_hidden(PurePosixPath("Thumbs.db"))
    assert is_hidden(PurePosixPath("Python/old.zip"))
    assert is_hidden(PurePosixPath(".teaching-tools/tags.json"))
    assert not is_hidden(PurePosixPath("Python/while_loops.py"))
    assert not is_hidden(PurePosixPath("Python/cloud_file.py"))


def test_scan_classifies_and_detects_placeholders(resources_root: Path) -> None:
    found = {r.rel_path: r for r in scan(resources_root)}
    assert "Python/Python_Course/while_loops.py" in found
    assert found["Python/Python_Course/while_loops.py"].kind == "python"
    assert found["Python/Python_Course/while_loops.pptx"].kind == "office"
    assert found["Python/__pycache__/junk.cpython-313.pyc"].hidden
    assert found["Python/old.zip"].hidden
    cloud = found["Python/cloud_file.py"]
    assert cloud.cloud_only and cloud.kind == "python" and not cloud.hidden
    assert ".cloud_file.py.icloud" not in {r.name for r in found.values()}
