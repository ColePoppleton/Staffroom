import errno
from pathlib import Path

import pytest

from teaching_tools.core.library.extract import CloudOnlyError, extract_text, read_text
from teaching_tools.core.library.model import Resource


def res(rel: str, kind: str) -> Resource:
    return Resource(rel, Path(rel).name, Path(rel).suffix, kind, 1, 0.0)  # type: ignore[arg-type]


def test_text_and_pdf(resources_root: Path) -> None:
    assert "while count" in (
        extract_text(res("Python/Python_Course/while_loops.py", "python"), resources_root) or ""
    )
    assert "OCR booklet" in (
        extract_text(res("Python/OCR Booklet/booklet.pdf", "pdf"), resources_root) or ""
    )
    assert extract_text(res("Python/scan_only.pdf", "pdf"), resources_root) is None  # no text layer


def test_office_is_never_parsed(resources_root: Path) -> None:
    assert (
        extract_text(res("Python/Python_Course/while_loops.pptx", "office"), resources_root) is None
    )
    assert extract_text(res("Python/OCR Booklet/booklet.doc", "office"), resources_root) is None


def test_deadlock_read_marks_cloud_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "evicted.py"
    p.write_text("x")
    real_open = Path.open

    def boom(self: Path, *a: object, **k: object) -> object:
        if self == p:
            raise OSError(errno.EDEADLK, "Resource deadlock avoided")
        return real_open(self, *a, **k)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "open", boom)
    with pytest.raises(CloudOnlyError):
        read_text(p)


def test_text_cap(tmp_path: Path) -> None:
    p = tmp_path / "big.txt"
    p.write_text("a" * 1000)
    assert len(read_text(p, cap=10)) == 10
