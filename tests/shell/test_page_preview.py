"""The page preview (#85): the PDF a run wrote, sheet and key, instead of an
ASCII rendering of it.

The widget renders known PDFs (written by the house-style exporter, as every
tool does), and the panels show it as two tabs, *Sheet* and *Key*."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from pypdf import PdfReader
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.export import Document, Numbered, PageBreak, Paragraph, Section, export
from staffroom.core.panel import Pages, pages_from
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets.page_preview import PagePreviewWidget, page_label, print_pdf

LONG_PAGES = 17  # the audit's long bugs sheet


def write_sheet(folder: Path, stem: str, pages: int = 1) -> list[Path]:
    """A sheet of ``pages`` pages and a one-page key, as PDFs."""
    blocks: list[object] = []
    for n in range(pages):
        if n:
            blocks.append(PageBreak())
        blocks.append(Paragraph(f"Page {n + 1} of the sheet"))
    doc = Document(
        title="Fake sheet",
        sections=[
            Section(blocks=blocks),  # type: ignore[arg-type]
            Section(blocks=[Numbered(("42",))], answers=True, title="Answers"),
        ],
    )
    return export(doc, folder, stem, ("pdf",))


@pytest.fixture
def preview(qtbot: QtBot) -> PagePreviewWidget:
    widget = PagePreviewWidget()
    qtbot.addWidget(widget)
    widget.resize(760, 560)
    widget.show()
    return widget


def test_renders_the_sheet_and_the_key(
    preview: PagePreviewWidget, qtbot: QtBot, tmp_path: Path
) -> None:
    files = write_sheet(tmp_path, "fake", pages=2)
    preview.set_pages(pages_from(files))
    assert preview.has_pdf() and preview.page_count("sheet") == 2
    assert preview.page_count("key") == 1
    # Opens on the sheet's first page, the page drawn by Qt's PDF view.
    assert (preview.part, preview.page) == ("sheet", 0)
    assert preview.canvas.document() is preview.parts["sheet"].document
    assert preview.model.rowCount() == 3  # thumbnails: sheet 1, sheet 2, key 1
    labels = [preview.model.index(r).data() for r in range(3)]
    assert labels == ["Sheet · page 1", "Sheet · page 2", "Key · page 1"]
    qtbot.waitUntil(lambda: not preview.busy() and len(preview.model.images) == 3, timeout=10000)
    # The key: its own document, its own file.
    preview.show_part("key")
    assert preview.canvas.document() is preview.parts["key"].document
    assert preview.path() == tmp_path / "fake_key.pdf"
    assert preview.rail.currentIndex().row() == 2


def test_a_thumbnail_moves_the_large_page(
    preview: PagePreviewWidget, tmp_path: Path, qtbot: QtBot
) -> None:
    preview.set_pages(pages_from(write_sheet(tmp_path, "fake", pages=3)))
    preview.rail.clicked.emit(preview.model.index(2))  # sheet page 3
    assert (preview.part, preview.page) == ("sheet", 2)
    assert preview.canvas.pageNavigator().currentPage() == 2
    with qtbot.waitSignal(preview.part_requested) as asked:
        preview.rail.clicked.emit(preview.model.index(3))  # the key's page
    assert asked.args == ["key"]
    assert preview.part == "key"  # nobody switched tabs for it: it switches itself


def test_thumbnails_are_lazy_so_a_long_sheet_stays_quick(
    preview: PagePreviewWidget, tmp_path: Path, qtbot: QtBot
) -> None:
    files = write_sheet(tmp_path, "long_bugs", pages=LONG_PAGES)
    started = time.perf_counter()
    preview.set_pages(pages_from(files))
    QApplication.processEvents()
    elapsed = time.perf_counter() - started
    assert preview.page_count("sheet") == LONG_PAGES
    # Only the thumbnails in view were asked for; the rest wait for a scroll.
    assert 0 < len(preview.model.requested) < LONG_PAGES
    assert elapsed < 1.0, f"set_pages took {elapsed:.2f}s"
    qtbot.waitUntil(lambda: not preview.busy(), timeout=10000)
    preview.show_part("key")  # scrolls the rail to the key's thumbnail...
    QApplication.processEvents()
    qtbot.waitUntil(lambda: ("key", 0) in preview.model.images, timeout=10000)  # ...drawn then


def test_word_only_shows_a_note_and_the_text_not_an_empty_page(
    preview: PagePreviewWidget, tmp_path: Path
) -> None:
    pages = pages_from(
        [tmp_path / "s.docx", tmp_path / "s_key.docx"], sheet_text="SHEET", key_text="KEY"
    )
    preview.set_pages(pages)
    assert not preview.has_pdf()
    assert preview.stack.currentWidget() is preview._fallback
    assert "docx only" in preview.note.text()
    assert preview.text.toPlainText() == "SHEET"
    preview.show_part("key")
    assert preview.text.toPlainText() == "KEY"
    assert preview.has_part("key")


def test_an_unreadable_pdf_says_so(preview: PagePreviewWidget, tmp_path: Path) -> None:
    broken = tmp_path / "broken.pdf"
    broken.write_text("not a pdf", encoding="utf-8")
    preview.set_pages(Pages(sheet=broken))
    assert not preview.has_pdf()
    assert "Could not open the PDF" in preview.note.text()


def test_rerun_lets_go_of_the_files(preview: PagePreviewWidget, tmp_path: Path) -> None:
    files = write_sheet(tmp_path, "fake")
    preview.set_pages(pages_from(files))
    preview.clear()
    assert not preview.parts and preview.model.rowCount() == 0
    # The documents were read into memory: rewriting the file under them is safe.
    preview.set_pages(pages_from(files))
    files[0].write_bytes(b"")
    QApplication.processEvents()
    assert preview.page_count("sheet") == 1


def test_open_pdf_asks_for_the_shown_part(
    preview: PagePreviewWidget, tmp_path: Path, qtbot: QtBot
) -> None:
    preview.set_pages(pages_from(write_sheet(tmp_path, "fake")))
    preview.show_part("key")
    with qtbot.waitSignal(preview.open_requested) as opened:
        preview.open_button.click()
    assert opened.args == [tmp_path / "fake_key.pdf"]


def test_print_draws_every_page_on_the_printer(tmp_path: Path, qtbot: QtBot) -> None:
    widget = PagePreviewWidget()
    qtbot.addWidget(widget)
    widget.set_pages(pages_from(write_sheet(tmp_path, "fake", pages=2)))
    printer = QPrinter(QPrinter.PrinterMode.ScreenResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setFullPage(True)
    printer.setOutputFileName(str(tmp_path / "printed.pdf"))
    assert print_pdf(widget.parts["sheet"].document, printer) == 2
    assert len(PdfReader(tmp_path / "printed.pdf").pages) == 2
    printer.setOutputFileName(str(tmp_path / "one.pdf"))
    assert print_pdf(widget.parts["sheet"].document, printer, 1, 1) == 1


def test_page_label() -> None:
    assert page_label("sheet", 0) == "Sheet · page 1"
    assert page_label("key", 2) == "Key · page 3"


# ---------------------------------------------------------------- in the panels
@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False, first_run=False)
    qtbot.addWidget(win)
    win.resize(1240, 780)
    win.show()
    return win


def open_tool(window: MainWindow, name: str) -> ToolPanel:
    window.sidebar.select(name)
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == name
    return panel


def run(panel: ToolPanel, qtbot: QtBot) -> None:
    with qtbot.waitSignal(panel.run_finished, timeout=60000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.strip.text()


def visible_tabs(panel: ToolPanel) -> list[str]:
    tabs = panel.results.tabs
    assert tabs is not None
    return [tabs.tabText(i) for i in range(tabs.count()) if tabs.isTabVisible(i)]


def test_worksheet_shows_sheet_and_key_tabs_with_page_counts(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    panel = open_tool(window, "worksheet")
    assert visible_tabs(panel) == ["Sheet", "Key"]
    run(panel, qtbot)
    assert visible_tabs(panel) == ["Sheet · 1 page", "Key · 1 page"]
    pane = panel.results
    preview = pane.page_previews["pages"]
    assert preview.isVisible() and preview.part == "sheet"
    assert pane.page_names["pages"].text() == "binary_medium_s42.pdf"
    # The Key tab shows the key file, in the same preview.
    assert pane.tabs is not None
    pane.tabs.setCurrentIndex(1)
    assert preview.isVisible() and preview.part == "key"
    assert preview.canvas.document() is preview.parts["key"].document
    assert pane.page_names["pages"].text() == "binary_medium_s42_key.pdf"
    # A sheet thumbnail clicked from the Key tab goes back to the Sheet tab.
    preview.rail.clicked.emit(preview.model.index(0))
    assert pane.tabs.currentIndex() == 0 and preview.part == "sheet"


def test_open_pdf_hands_the_file_to_its_app(
    window: MainWindow, qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel = open_tool(window, "worksheet")
    run(panel, qtbot)
    opened: list[Path] = []
    monkeypatch.setattr(panel, "open_file", opened.append)
    panel.results.open_requested.disconnect()
    panel.results.open_requested.connect(panel.open_file)
    panel.results.page_previews["pages"].open_button.click()
    assert opened == [tmp_path / "out" / "binary_medium_s42.pdf"]


def test_docx_only_shows_the_note(window: MainWindow, qtbot: QtBot) -> None:
    panel = open_tool(window, "worksheet")
    panel.forms["options"].set_field("formats", "docx")
    run(panel, qtbot)
    preview = panel.results.page_previews["pages"]
    assert not preview.has_pdf() and preview.isVisible()
    assert "pdf or both" in preview.note.text()
    assert "Worksheet: Binary" in preview.text.toPlainText()
    assert visible_tabs(panel) == ["Sheet", "Key"]


def test_quiz_do_now_shows_pages_and_kahoot_shows_paste_text(
    window: MainWindow, qtbot: QtBot
) -> None:
    from staffroom.core.paths import examples_dir

    panel = open_tool(window, "quiz")
    panel.set_input_path("source", examples_dir() / "question_bank.md")
    assert visible_tabs(panel) == ["Chosen questions", "Sheet", "Key"]  # Paste text waits
    form = panel.forms["options"]
    form.set_field("fmt", "donow")
    run(panel, qtbot)
    preview = panel.results.page_previews["pages"]
    sheet, key = preview.page_count("sheet"), preview.page_count("key")
    assert sheet >= 1 and key >= 1
    assert visible_tabs(panel) == [
        "Chosen questions",
        f"Sheet · {sheet} page{'s' if sheet > 1 else ''}",
        f"Key · {key} page{'s' if key > 1 else ''}",
    ]
    form.set_field("fmt", "kahoot")
    run(panel, qtbot)
    assert visible_tabs(panel) == ["Chosen questions", "Paste text"]
    assert "Question - max 120" in panel.results.text_views["paste"].toPlainText()
