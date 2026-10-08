"""Root conftest: shared fixtures for tests/ and every tool's tests/. Every test
gets an isolated config/log home so nothing touches ~/.config/staffroom."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from pypdf import PdfWriter

from staffroom.core import paths
from staffroom.core.library.service import LibraryService

EXAMPLES = paths.examples_dir()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    home = tmp_path / "staffroom-home"
    monkeypatch.setenv("STAFFROOM_HOME", str(home))
    yield home


@pytest.fixture
def example_marks() -> Path:
    return EXAMPLES / "marks_10x.csv"


@pytest.fixture
def example_marks_max() -> Path:
    return EXAMPLES / "marks_10x_max.csv"


@pytest.fixture(scope="session", autouse=True)
def _offscreen_qt() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


# ---------------------------------------------------------------- library fixtures
# A small fake resources root exercising every rule: kinds, hidden cruft, an
# iCloud placeholder, a PDF with a text layer and one without, an Office file
# that must never be parsed.
def make_pdf(path: Path, text: str | None) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if text:
        # pypdf cannot author text easily; emulate a text layer via metadata-free
        # content stream using the lowest-level API.
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

        page = writer.pages[0]
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_ref = writer._add_object(font)
        resources = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
        )
        page[NameObject("/Resources")] = resources
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    with path.open("wb") as fh:
        writer.write(fh)


@pytest.fixture
def resources_root(tmp_path: Path) -> Path:
    root = tmp_path / "Resources"
    (root / "Python" / "Python_Course").mkdir(parents=True)
    (root / "Python" / "OCR Booklet").mkdir(parents=True)
    (root / "Python" / "__pycache__").mkdir()
    (root / "Scratch").mkdir()
    (root / ".idea").mkdir()

    (root / "Python" / "Python_Course" / "while_loops.py").write_text(
        "count = 0\nwhile count < 10:\n    print(count)\n    count += 1\n"
    )
    (root / "Python" / "Python_Course" / "while_loops.pptx").write_bytes(
        b"PK\x03\x04 not really a pptx"
    )
    (root / "Python" / "OCR Booklet" / "exercise_3a.py").write_text(
        "# Exercise 3a: keep asking while the answer is wrong\n"
        "answer = ''\nwhile answer != 'yes':\n    answer = input()\n"
    )
    (root / "Python" / "OCR Booklet" / "booklet.doc").write_bytes(b"\xd0\xcf\x11\xe0 old word")
    (root / "Python" / "notes.md").write_text("# Notes\n\nFor loops versus while loops.\n")
    (root / "Python" / "marks.csv").write_text("# FAKE DATA\nq1,q2\n1,2\n")
    (root / "Python" / "readme.txt").write_text("Plain text about iteration.\n")
    (root / "Python" / "__pycache__" / "junk.cpython-313.pyc").write_bytes(b"\x00")
    (root / "Python" / ".DS_Store").write_bytes(b"\x00")
    (root / "Python" / "old.zip").write_bytes(b"PK")
    (root / ".idea" / "workspace.xml").write_text("<x/>")
    (root / "Scratch" / "flappy.sb").write_bytes(b"ScratchV02")
    (root / "Scratch" / "diagram.png").write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000d49444154789c636000010000050001a5f645400000000049454e44ae426082"
        )
    )
    make_pdf(root / "Python" / "OCR Booklet" / "booklet.pdf", "while loops in the OCR booklet")
    make_pdf(root / "Python" / "scan_only.pdf", None)
    # An evicted iCloud file: only the placeholder exists.
    (root / "Python" / ".cloud_file.py.icloud").write_bytes(b"bplist00")
    return root


@pytest.fixture
def opened() -> list[list[str]]:
    return []


@pytest.fixture
def service(resources_root: Path, tmp_path: Path, opened: list[list[str]]) -> LibraryService:
    svc = LibraryService(
        resources_root, tmp_path / "library.db", opener=lambda a: opened.append(list(a))
    )
    svc.index()
    return svc
