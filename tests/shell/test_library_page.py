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


@pytest.fixture
def window(qtbot: QtBot, service: LibraryService, resources_root: Path) -> MainWindow:
    config = load_config()
    config.general.resources_root = str(resources_root)
    win = MainWindow(config, library=service, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    return win


def test_resources_mode_shows_tree_and_page(window: MainWindow) -> None:
    window.sidebar.set_mode("resources")
    assert window.stack.currentWidget() is window.library_page
    assert window.config.general.sidebar_mode == "resources"
    model = window.sidebar.resources.model
    assert model.rowCount() >= 2  # Python/, Scratch/
    top = [model.item(i).text() for i in range(model.rowCount())]
    assert top[:2] == ["Python", "Scratch"]
    # hidden cruft is absent by default
    flags = Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive
    assert not model.match(model.index(0, 0), REL_PATH_ROLE, "Python/old.zip", 1, flags)


def test_show_hidden_toggle(window: MainWindow) -> None:
    window.sidebar.set_mode("resources")
    window.sidebar.resources.hidden.setChecked(True)
    model = window.sidebar.resources.model
    flags = Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive
    assert model.match(model.index(0, 0), REL_PATH_ROLE, "Python/old.zip", 1, flags)
    assert window.config.general.show_hidden is True


def test_select_python_file_previews_code(window: MainWindow) -> None:
    window.sidebar.set_mode("resources")
    window.sidebar.resources.select("Python/Python_Course/while_loops.py")
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
    window.sidebar.set_mode("resources")
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
    window.sidebar.set_mode("resources")
    window.sidebar.resources.search.setText("while")
    results = window.library_page.results
    assert results.isVisibleTo(window.library_page)
    rels = [results.item(i).data(Qt.ItemDataRole.UserRole) for i in range(results.count())]
    assert "Python/Python_Course/while_loops.py" in rels
    assert "Python/OCR Booklet/booklet.pdf" in rels
    results.setCurrentRow(0)
    assert window.library_page.preview.resource is not None
    window.sidebar.resources.kind.setCurrentIndex(window.sidebar.resources.kind.findData("pdf"))
    rels = [results.item(i).data(Qt.ItemDataRole.UserRole) for i in range(results.count())]
    assert all(r.endswith(".pdf") for r in rels if r)
    window.sidebar.resources.search.setText("zzzznothing")
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
        window.sidebar.resources.reindex.click()
    assert window.library.get("Python/new_file.py") is not None
    assert "files" in window.sidebar.resources.status.text()


def test_tools_mode_restores_tool(window: MainWindow) -> None:
    window.sidebar.select("hello")
    window.sidebar.set_mode("resources")
    assert window.stack.currentWidget() is window.library_page
    window.sidebar.set_mode("tools")
    assert window.stack.currentWidget() is window.panel_for("hello")
