"""House style: every renderer produces a readable file from the same model;
the key splits off cleanly."""

from datetime import date
from pathlib import Path

import pytest
from docx import Document as DocxReader
from pypdf import PdfReader

from teaching_tools.core.export import (
    Code,
    Document,
    Heading,
    HintBox,
    Numbered,
    PageBreak,
    Paragraph,
    TableBlock,
    export,
    render,
    to_text,
)


@pytest.fixture
def doc() -> Document:
    d = Document(
        title="Worksheet: Loops", topic="Python", date=date(2026, 10, 7), subtitle="seed 7"
    )
    s = d.section()
    s.add(Paragraph("Answer all questions.", style="instruction"))
    s.add(Heading("Part A"))
    s.add(Numbered(("What is a loop?", "Write a while loop."), answer_lines=2))
    s.add(Code("while x < 3:\n    x += 1", caption="Listing 1"))
    s.add(TableBlock(("A", "B", "Q"), (("0", "0", ""), ("0", "1", "")), monospace=True))
    s.add(HintBox("Count from zero."))
    s.add(PageBreak())
    k = d.section("Answer key", answers=True)
    k.add(Numbered(("Repetition.", "see listing")))
    return d


def test_sheet_and_key_split(doc: Document) -> None:
    assert doc.has_answers
    assert [s.answers for s in doc.sheet().sections] == [False]
    key = doc.key()
    assert key.title.endswith("Answer key") and [s.title for s in key.sections] == ["Answer key"]


def test_text_rendering(doc: Document) -> None:
    text = to_text(doc)
    assert text.startswith(
        "Worksheet: Loops\n================\nPython   ·   07 October 2026   ·   seed 7"
    )
    assert "  1. What is a loop?" in text and "____" in text
    assert "    while x < 3:" in text
    assert "A  B  Q" in text and "[Hint] Count from zero." in text
    assert "ANSWER KEY" in text


def test_docx_round_trip(doc: Document, tmp_path: Path) -> None:
    path = render(doc.sheet(), tmp_path / "sheet.docx")
    read = DocxReader(str(path))
    texts = [p.text for p in read.paragraphs]
    assert "Worksheet: Loops" in texts
    assert any("1.  What is a loop?" in t for t in texts)
    assert any("while x < 3:" in t for t in texts)
    header = read.sections[0].header.paragraphs[0].text
    assert "Worksheet: Loops" in header and "07 October 2026" in header
    footer_xml = read.sections[0].footer.paragraphs[0]._p.xml
    assert "PAGE" in footer_xml and "NUMPAGES" in footer_xml
    assert read.tables and read.tables[0].rows[0].cells[2].text == "Q"


def test_pdf_round_trip(doc: Document, tmp_path: Path) -> None:
    path = render(doc, tmp_path / "all.pdf")
    reader = PdfReader(str(path))
    assert len(reader.pages) >= 2  # page break + key
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Worksheet: Loops" in text and "What is a loop?" in text
    assert "while x < 3:" in text and "Count from zero." in text
    assert "Page 1" in text and "Answer key" in text


def test_export_writes_sheet_and_key_per_format(doc: Document, tmp_path: Path) -> None:
    written = export(doc, tmp_path, "loops")
    assert [p.name for p in written] == [
        "loops.docx",
        "loops_key.docx",
        "loops.pdf",
        "loops_key.pdf",
    ]
    only = export(doc, tmp_path, "loops2", formats=("pdf",), split_key=False)
    assert [p.name for p in only] == ["loops2.pdf"]
    with pytest.raises(ValueError, match="unsupported"):
        render(doc, tmp_path / "x.odt")
