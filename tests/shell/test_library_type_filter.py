"""The Library's type filter narrows the tree, not only the search results
(#122). Type, tags and query always combine; the narrowed tree opens all the
way down; the footer starts with what is shown (``2 Python files tagged
loops``) while the sidebar count and the header stay the library's own
(#30). The fixture files are invented (``# FAKE DATA``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QModelIndex, Qt
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.library.service import LibraryService
from staffroom.shell.library.page import REL_ROLE
from staffroom.shell.library.tree import REL_PATH_ROLE
from staffroom.shell.main_window import MainWindow
from staffroom.shell.sidebar import LIBRARY

FILES = {
    "Python/Year 9/average.py": "# FAKE DATA\nscores = [4, 7]\nfor s in scores:\n    print(s)\n",
    "Python/Year 10/temperature.py": "# FAKE DATA\nwhile True:\n    break\n",
    "Python/Year 10/loops_notes.md": "# FAKE DATA\n\nFor and while loops.\n",
    "Theory/binary_recap.md": "# FAKE DATA\n\nBinary place value.\n",
    "Theory/hex_practice.txt": "# FAKE DATA\nHex practice: 0x1F.\n",
}
TAGS = {
    "Python/Year 9/average.py": "loops, ks3",
    "Python/Year 10/temperature.py": "loops",
    "Python/Year 10/loops_notes.md": "loops",
    "Theory/binary_recap.md": "ks3",
}
PYTHON = {"Python/Year 9/average.py", "Python/Year 10/temperature.py"}


@pytest.fixture
def fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "FakeResources"
    for rel, text in FILES.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


@pytest.fixture
def window(qtbot: QtBot, fake_root: Path, tmp_path: Path) -> MainWindow:
    svc = LibraryService(fake_root, tmp_path / "library.db", opener=lambda _a: None)
    svc.index()
    for rel, tags in TAGS.items():
        svc.set_tags(rel, tags)
    config = load_config()
    config.general.resources_root = str(fake_root)
    win = MainWindow(config, library=svc, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    win.show_library()
    return win


def choose_kind(win: MainWindow, kind: str) -> None:
    win.resources.kind.setCurrentIndex(win.resources.kind.findData(kind))


def tree_files(win: MainWindow) -> set[str]:
    model = win.resources.model
    found: set[str] = set()

    def walk(parent: QModelIndex) -> None:
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            rel = index.data(REL_PATH_ROLE)
            if rel:
                found.add(str(rel))
            walk(index)

    walk(QModelIndex())
    return found


def result_files(win: MainWindow) -> set[str]:
    results = win.library_page.results
    return {
        str(results.item(i).data(REL_ROLE))
        for i in range(results.count())
        if results.item(i).data(REL_ROLE)
    }


def is_open_down_to(win: MainWindow, rel: str) -> bool:
    model = win.resources.model
    match = model.match(
        model.index(0, 0),
        REL_PATH_ROLE,
        rel,
        1,
        Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
    )[0]
    parent = match.parent()
    while parent.isValid():
        if not win.resources.tree.isExpanded(parent):
            return False
        parent = parent.parent()
    return True


def test_choosing_a_type_narrows_the_tree_without_a_query(window: MainWindow) -> None:
    assert window.library_page.query == ""
    assert tree_files(window) == set(FILES)
    choose_kind(window, "python")
    assert tree_files(window) == PYTHON
    # The tree, not the results list, is what the column shows.
    assert window.resources.views.currentWidget() is window.resources.tree
    assert all(is_open_down_to(window, rel) for rel in PYTHON)
    choose_kind(window, "text")
    assert tree_files(window) == {"Theory/hex_practice.txt"}
    choose_kind(window, "pdf")
    assert tree_files(window) == set()
    choose_kind(window, "all")
    assert tree_files(window) == set(FILES)


def test_footer_says_what_is_shown(window: MainWindow) -> None:
    status = window.resources.status
    library_line = status.text()
    assert library_line == "5 files"
    choose_kind(window, "python")
    assert status.text() == "2 Python files\n5 files"
    window.resources.tag_filter.toggle_tag("ks3")
    assert status.text() == "1 Python file tagged ks3\n5 files"
    choose_kind(window, "all")
    assert status.text() == "2 files tagged ks3\n5 files"
    window.resources.tag_filter.clear()
    assert status.text() == library_line


def test_sidebar_and_header_stay_the_librarys_count(window: MainWindow) -> None:
    """#30: one definition of the count; a filter narrows only the tree."""
    library_item = window.sidebar.item(LIBRARY)
    assert library_item is not None
    header = window.library_page.index_status.text()
    choose_kind(window, "python")
    window.resources.tag_filter.toggle_tag("loops")
    assert library_item.count.text() == str(len(FILES))
    assert window.library_page.index_status.text() == header
    assert header.startswith("5 files")


def test_type_tags_and_query_always_combine(window: MainWindow) -> None:
    window.resources.tag_filter.toggle_tag("loops")
    assert tree_files(window) == {*PYTHON, "Python/Year 10/loops_notes.md"}
    choose_kind(window, "python")
    assert tree_files(window) == PYTHON
    choose_kind(window, "markdown")
    assert tree_files(window) == {"Python/Year 10/loops_notes.md"}
    assert window.resources.status.text().startswith("1 Markdown file tagged loops\n")
    # The query shows results through the same two filters ...
    window.resources.search.setText("FAKE")
    assert result_files(window) == {"Python/Year 10/loops_notes.md"}
    choose_kind(window, "python")
    assert result_files(window) == PYTHON
    # ... and clearing it brings back the tree, still narrowed by both.
    window.resources.search.setText("")
    assert window.resources.views.currentWidget() is window.resources.tree
    assert tree_files(window) == PYTHON
    assert window.resources.status.text().startswith("2 Python files tagged loops\n")


def test_type_survives_hidden_and_tag_edits(window: MainWindow) -> None:
    choose_kind(window, "python")
    window.resources.hidden.setChecked(True)
    assert tree_files(window) == PYTHON
    window.resources.hidden.setChecked(False)
    assert tree_files(window) == PYTHON
    # A tag edit in the preview refreshes the counts, not the type.
    window.library_page.show_resource("Python/Year 10/temperature.py")
    window.library_page.preview.tags.add_tag("gcse")
    assert tree_files(window) == PYTHON
    assert window.resources.status.text().startswith("2 Python files\n")


def test_the_resources_folder_is_not_written(window: MainWindow, fake_root: Path) -> None:
    before = {p: p.read_bytes() for p in fake_root.rglob("*") if p.is_file()}
    choose_kind(window, "python")
    window.resources.tag_filter.toggle_tag("loops")
    window.resources.search.setText("FAKE")
    choose_kind(window, "all")
    after = {p: p.read_bytes() for p in fake_root.rglob("*") if p.is_file()}
    assert after == before
