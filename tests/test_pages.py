"""The page preview's data (#85): which written files are the sheet and the
key, and what a run that wrote no PDF shows instead. Qt-free."""

from __future__ import annotations

from pathlib import Path

from staffroom.core.panel import (
    NO_PDF_NOTE,
    PagePreview,
    Pages,
    PanelSpec,
    TextView,
    main_outputs,
    pages_from,
)
from staffroom.core.plugin import RunResult

OUT = Path("/out")


def test_sheet_and_key_from_the_written_files() -> None:
    files = [
        OUT / "binary_s42.docx",
        OUT / "binary_s42_key.docx",
        OUT / "binary_s42.pdf",
        OUT / "binary_s42_key.pdf",
    ]
    pages = pages_from(files)
    assert pages == Pages(sheet=OUT / "binary_s42.pdf", key=OUT / "binary_s42_key.pdf")
    assert pages.has_pdf


def test_key_order_and_other_files_do_not_matter() -> None:
    files = [OUT / "y9_bugs_key.pdf", OUT / "y9_bug1.py", OUT / "y9_bugs.pdf"]
    assert pages_from(files) == Pages(sheet=OUT / "y9_bugs.pdf", key=OUT / "y9_bugs_key.pdf")


def test_a_sheet_without_a_key() -> None:
    assert pages_from([OUT / "notes.pdf"]) == Pages(sheet=OUT / "notes.pdf")


def test_a_pdf_whose_name_ends_in_key_but_has_no_sheet_is_the_sheet() -> None:
    assert pages_from([OUT / "monkey.pdf"]).sheet == OUT / "monkey.pdf"
    assert pages_from([OUT / "answer_key.pdf"]) == Pages(sheet=OUT / "answer_key.pdf")


def test_word_only_gives_a_note_and_the_text_instead() -> None:
    pages = pages_from(
        [OUT / "s.docx", OUT / "s_key.docx"], sheet_text="Sheet text", key_text="Key text"
    )
    assert not pages.has_pdf
    assert pages.note == NO_PDF_NOTE
    assert "docx" in pages.note and "pdf or both" in pages.note
    assert (pages.sheet_text, pages.key_text) == ("Sheet text", "Key text")


def test_the_text_is_dropped_when_there_are_pages() -> None:
    pages = pages_from([OUT / "s.pdf"], sheet_text="Sheet text")
    assert pages.sheet_text == "" and pages.note == ""


def test_run_result_carries_pages_by_key() -> None:
    result = RunResult(pages={"pages": Pages(sheet=OUT / "s.pdf")})
    assert result.pages["pages"].sheet == OUT / "s.pdf"
    assert RunResult().pages == {}


def test_page_preview_is_a_main_view() -> None:
    spec = PanelSpec(
        title="T",
        outputs=(PagePreview(key="pages"), TextView(key="paste", optional=True)),
    )
    assert [w.key for w in main_outputs(spec.outputs)] == ["pages", "paste"]
