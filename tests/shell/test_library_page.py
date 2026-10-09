"""The Resources side of the launcher: tree from the index, search results,
previews per kind, the open-externally card, and tag saving."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.library.service import LibraryService
from staffroom.shell.library.tree import REL_PATH_ROLE
from staffroom.shell.main_window import MainWindow
from staffroom.shell.sidebar import LIBRARY


@pytest.fixture
def window(qtbot: QtBot, service: LibraryService, resources_root: Path) -> MainWindow:
    config = load_config()
    config.general.resources_root = str(resources_root)
    win = MainWindow(config, library=service, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    return win


def test_library_shows_tree_and_page(window: MainWindow) -> None:
    window.show_library()
    assert window.stack.currentWidget() is window.library_view
    assert window.sidebar.current() == LIBRARY
    assert window.config.general.sidebar_mode == "resources"
    model = window.resources.model
    assert model.rowCount() >= 2  # Python/, Scratch/
    # Indexes, not items: a QStandardItem wrapper can outlive its item (#49).
    top = [model.index(i, 0).data() for i in range(model.rowCount())]
    assert top[:2] == ["Python", "Scratch"]
    # hidden cruft is absent by default
    flags = Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive
    assert not model.match(model.index(0, 0), REL_PATH_ROLE, "Python/old.zip", 1, flags)


def test_show_hidden_toggle(window: MainWindow) -> None:
    window.show_library()
    window.resources.hidden.setChecked(True)
    model = window.resources.model
    flags = Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive
    assert model.match(model.index(0, 0), REL_PATH_ROLE, "Python/old.zip", 1, flags)
    assert window.config.general.show_hidden is True


def test_select_python_file_previews_code(window: MainWindow) -> None:
    window.show_library()
    window.resources.select("Python/Python_Course/while_loops.py")
    preview = window.library_page.preview
    assert preview.resource is not None
    assert preview.resource.rel_path == "Python/Python_Course/while_loops.py"
    assert preview.content.currentWidget() is preview.code
    assert "while count < 10" in preview.code.toPlainText()
    assert preview.highlighter is not None
    assert preview.chip.text() == "Python"


def test_pptx_shows_card_and_opens_externally(
    window: MainWindow, opened: list[list[str]], resources_root: Path
) -> None:
    window.show_library()
    window.library_page.show_resource("Python/Python_Course/while_loops.pptx")
    preview = window.library_page.preview
    assert preview.content.currentWidget() is preview.card
    assert "PowerPoint" in preview.card_title.text()
    assert "never parsed" in preview.card_text.text()
    preview.card_button.click()
    assert opened == [[str(resources_root / "Python/Python_Course/while_loops.pptx")]]


def test_cloud_only_banner(window: MainWindow) -> None:
    window.library_page.show_resource("Python/cloud_file.py")
    preview = window.library_page.preview
    assert preview.cloud_banner.isVisibleTo(preview)
    assert preview.content.currentWidget() is preview.card


def test_pdf_and_image_previews(window: MainWindow) -> None:
    page = window.library_page
    page.show_resource("Python/OCR Booklet/booklet.pdf")
    assert page.preview.content.currentWidget() is page.preview.text
    assert "OCR booklet" in page.preview.text.toPlainText()
    page.show_resource("Python/scan_only.pdf")
    assert "No text layer" in page.preview.text.toPlainText()
    page.show_resource("Scratch/diagram.png")
    assert page.preview.content.currentWidget() is page.preview.image


def test_search_lists_results_and_selecting_previews(window: MainWindow) -> None:
    window.show_library()
    window.resources.search.setText("while")
    results = window.library_page.results
    assert results.isVisibleTo(window.library_page)
    # item(i) wrappers are dropped with each comprehension; the list is not cleared meanwhile (#54).
    rels = [results.item(i).data(Qt.ItemDataRole.UserRole) for i in range(results.count())]
    assert "Python/Python_Course/while_loops.py" in rels
    assert "Python/OCR Booklet/booklet.pdf" in rels
    results.setCurrentRow(0)
    assert window.library_page.preview.resource is not None
    window.resources.kind.setCurrentIndex(window.resources.kind.findData("pdf"))
    rels = [results.item(i).data(Qt.ItemDataRole.UserRole) for i in range(results.count())]
    assert all(r.endswith(".pdf") for r in rels if r)
    window.resources.search.setText("zzzznothing")
    assert results.count() == 1 and results.item(0).text() == "No matches"


def test_tag_editor_saves_to_sidecar(window: MainWindow, resources_root: Path) -> None:
    page = window.library_page
    page.show_resource("Python/notes.md")
    page.preview.tags_edit.setText("Loops, KS3")
    page.preview.notes_edit.setPlainText("Starter for Y8")
    page.preview.save_button.click()
    assert page.preview.tags_edit.text() == "loops, ks3"
    assert (resources_root / ".staffroom" / "tags.json").exists()
    assert window.library.tag_entry("Python/notes.md").notes == "Starter for Y8"
    # The resource itself was not written.
    assert (resources_root / "Python" / "notes.md").read_text().startswith("# Notes")


def test_reindex_in_background(window: MainWindow, qtbot: QtBot, resources_root: Path) -> None:
    (resources_root / "Python" / "new_file.py").write_text("while True: pass\n")
    with qtbot.waitSignal(window.library_page.indexed, timeout=10000):
        window.resources.reindex.click()
    assert window.library.get("Python/new_file.py") is not None
    assert "files" in window.resources.status.text()


def test_library_and_a_tool_are_two_destinations(window: MainWindow) -> None:
    """The library is a place in the sidebar, not a mode: going there and
    back to a tool is two clicks, and the highlight follows each time."""
    assert window.sidebar.select("marks")  # a listed tool; hello is hidden
    window.show_library()
    assert window.stack.currentWidget() is window.library_view
    assert window.sidebar.current() == LIBRARY
    assert window.sidebar.select("marks")
    assert window.stack.currentWidget() is window.panel_for("marks")
    assert window.sidebar.current() == "marks"
    assert window.config.general.sidebar_mode == "tools"


def test_typing_in_the_sidebar_search_continues_in_the_library(window: MainWindow) -> None:
    window.sidebar.select("marks")
    window.sidebar.search.setText("while")
    window.sidebar.search.textEdited.emit("while")
    assert window.stack.currentWidget() is window.library_view
    assert window.resources.search.text() == "while"
    assert window.library_page.query == "while"
    assert window.sidebar.search.text() == ""  # handed over, not duplicated


def test_library_row_counts_the_listed_files(window: MainWindow) -> None:
    """The number beside Library is the length of the tree's list (#30)."""
    library = window.sidebar.item(LIBRARY)
    assert library is not None
    listed = window.library.resources(include_hidden=window.config.general.show_hidden)
    assert listed and library.count.text() == str(len(listed))


def test_withheld_file_shows_banner_and_status(
    window: MainWindow, qtbot: QtBot, resources_root: Path
) -> None:
    (resources_root / "Python" / "task_submission.py").write_text(
        "# Candidate number: 4021\n# UPN: A123456789012\nprint(1)\n"
    )
    with qtbot.waitSignal(window.library_page.indexed, timeout=10000):
        window.resources.reindex.click()
    assert "1 name only" in window.resources.status.text()
    assert "pupil details" in window.resources.status.toolTip()
    assert "1 name only" in window.library_page.index_status.text()
    window.library_page.show_resource("Python/task_submission.py")
    preview = window.library_page.preview
    assert preview.withheld_banner.isVisibleTo(preview)
    assert not preview.cloud_banner.isVisibleTo(preview)
    window.library_page.show_resource("Python/notes.md")
    assert not preview.withheld_banner.isVisibleTo(preview)


def test_settings_exclusion_list_hides_folder_and_reindexes(
    window: MainWindow, qtbot: QtBot
) -> None:
    model = window.resources.model
    flags = Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive
    booklet = "Python/OCR Booklet/exercise_3a.py"
    assert model.match(model.index(0, 0), REL_PATH_ROLE, booklet, 1, flags)

    editor = window.settings.library_exclude
    editor.edit.setText("OCR Booklet")
    with qtbot.waitSignal(window.library_page.indexed, timeout=10000):
        editor.add_button.click()
    assert window.config.general.library_exclude == ["OCR Booklet"]
    assert editor.values() == ["OCR Booklet"]
    assert not model.match(model.index(0, 0), REL_PATH_ROLE, booklet, 1, flags)
    assert window.library.db.get(booklet) is None
    assert window.library.get("Python/notes.md") is not None

    editor.list.setCurrentRow(0)
    with qtbot.waitSignal(window.library_page.indexed, timeout=10000):
        editor.remove_button.click()
    assert window.config.general.library_exclude == []
    assert window.library.get(booklet) is not None


def test_settings_carries_the_stored_statement(window: MainWindow) -> None:
    text = window.settings.library_statement.text()
    assert "only ever read" in text
    assert "library.db" in text
    assert ".py, .txt, .md, .csv and .pdf" in text
    assert "full re-index drops the old entries" in text


def test_sidebar_footer_and_header_show_one_count(window: MainWindow) -> None:
    """#30: "563 files" in the sidebar against "587 files indexed" in the
    header was hidden cruft counted differently. Both now start with the one
    line ``LibraryService.counts`` produces, and the sidebar's number is the
    size of the tree it shows, with Hidden off and on."""
    window.show_library()
    panel, page, library = window.resources, window.library_page, window.library
    counts = library.counts()
    assert counts.hidden > 0 and counts.cloud_only > 0  # the fixture has both flavours

    line = counts.status_line(show_hidden=False)
    assert panel.status.text() == counts.status_line(show_hidden=False, sep="\n")
    assert page.index_status.text().startswith(line + "  ·  last index ")
    assert line.startswith(f"{counts.shown} files ({counts.hidden} hidden)")
    assert len(library.resources()) == counts.shown
    assert panel.status.toolTip() == page.index_status.toolTip() != ""

    panel.hidden.setChecked(True)
    line = counts.status_line(show_hidden=True)
    assert panel.status.text() == line == f"{counts.indexed} files (incl. {counts.hidden} hidden)"
    assert page.index_status.text().startswith(line + "  ·  last index ")
    assert len(library.resources(include_hidden=True)) == counts.indexed
