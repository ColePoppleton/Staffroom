"""The Library's Tags ▾ filter (#111): it lists the tags in use with their
counts, narrows the tree and the search results to files carrying every
chosen tag, combines with the type filter and the query, and follows tag
edits made in the preview. The fixture files are invented (``# FAKE DATA``)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QModelIndex, Qt
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.library.service import LibraryService
from staffroom.core.library.tags import TagCount
from staffroom.shell.library.page import REL_ROLE
from staffroom.shell.library.tag_filter import EMPTY_HINT, TagFilterButton, button_text
from staffroom.shell.library.tree import REL_PATH_ROLE
from staffroom.shell.main_window import MainWindow
from staffroom.shell.sidebar import LIBRARY

FILES = {
    "Python/Year 9/average.py": "# FAKE DATA\nscores = [4, 7]\nfor s in scores:\n    print(s)\n",
    "Python/Year 10/temperature.py": "# FAKE DATA\nwhile True:\n    break\n",
    "Theory/binary_recap.md": "# FAKE DATA\n\nBinary place value.\n",
    "Theory/hex_practice.txt": "# FAKE DATA\nHex practice: 0x1F.\n",
}
TAGS = {
    "Python/Year 9/average.py": "loops, ks3",
    "Python/Year 10/temperature.py": "loops, gcse",
    "Theory/binary_recap.md": "ks3",
}


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


def test_button_sits_beside_the_type_filter(window: MainWindow) -> None:
    column = window.resources
    assert column.tag_filter.parentWidget() is column.kind.parentWidget()
    assert column.tag_filter.text() == "Tags ▾"
    assert column.tag_filter.isVisible()
    kind, tags, hidden = (
        column.kind.geometry(),
        column.tag_filter.geometry(),
        column.hidden.geometry(),
    )
    assert kind.right() < tags.left() and tags.right() < hidden.left()
    assert abs(kind.center().y() - tags.center().y()) <= 2  # one row


def test_menu_lists_the_tags_in_use_with_counts(window: MainWindow) -> None:
    actions = window.resources.tag_filter.tag_actions()
    assert [a.text() for a in actions] == ["ks3  2", "loops  2", "gcse  1"]
    assert not any(a.isChecked() for a in actions)


def test_choosing_a_tag_narrows_the_tree(window: MainWindow) -> None:
    every = tree_files(window)
    assert every == set(FILES)
    window.resources.tag_filter.toggle_tag("loops")
    assert tree_files(window) == {"Python/Year 9/average.py", "Python/Year 10/temperature.py"}
    assert window.resources.tag_filter.text() == "loops ▾"
    assert window.resources.tag_filter.property("active") == "true"
    assert window.resources.status.text().startswith("2 files tagged loops\n")
    # Every chosen tag is required.
    window.resources.tag_filter.toggle_tag("gcse")
    assert tree_files(window) == {"Python/Year 10/temperature.py"}
    assert window.resources.tag_filter.text() == "loops +1 ▾"
    # The narrowed tree is open all the way down.
    match = window.resources.model.match(
        window.resources.model.index(0, 0),
        REL_PATH_ROLE,
        "Python/Year 10/temperature.py",
        1,
        Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
    )[0]
    assert window.resources.tree.isExpanded(match.parent())
    # The sidebar's count stays the library's own.
    library_item = window.sidebar.item(LIBRARY)
    assert library_item is not None and library_item.count.text() == str(len(FILES))
    window.resources.tag_filter.clear()
    assert tree_files(window) == every
    assert window.resources.tag_filter.text() == "Tags ▾"


def test_choosing_from_the_menu(window: MainWindow) -> None:
    tag_filter = window.resources.tag_filter
    ks3 = next(a for a in tag_filter.tag_actions() if a.data() == "ks3")
    ks3.trigger()
    assert tag_filter.chosen() == ["ks3"]
    assert tree_files(window) == {"Python/Year 9/average.py", "Theory/binary_recap.md"}
    assert [a.isChecked() for a in tag_filter.tag_actions()] == [True, False, False]
    assert "Show all files" in [a.text() for a in tag_filter.menu_.actions()]


def test_filter_combines_with_query_and_type(window: MainWindow) -> None:
    window.resources.search.setText("FAKE")
    assert result_files(window) == set(FILES)
    window.resources.tag_filter.toggle_tag("ks3")
    assert result_files(window) == {"Python/Year 9/average.py", "Theory/binary_recap.md"}
    window.resources.kind.setCurrentIndex(window.resources.kind.findData("python"))
    assert result_files(window) == {"Python/Year 9/average.py"}
    window.resources.tag_filter.toggle_tag("gcse")  # no python file has ks3 and gcse
    assert result_files(window) == set()


def test_tag_edits_in_the_preview_update_the_filter(window: MainWindow) -> None:
    tag_filter = window.resources.tag_filter
    tag_filter.toggle_tag("gcse")
    assert tree_files(window) == {"Python/Year 10/temperature.py"}

    window.library_page.show_resource("Theory/hex_practice.txt")
    window.library_page.preview.tags.add_tag("gcse")
    assert ("gcse", 2) in [(c.tag, c.count) for c in tag_filter.counts()]
    assert tree_files(window) == {"Python/Year 10/temperature.py", "Theory/hex_practice.txt"}

    # Removing the last use of a chosen tag drops it from the filter.
    for rel in ("Python/Year 10/temperature.py", "Theory/hex_practice.txt"):
        window.library_page.show_resource(rel)
        window.library_page.preview.tags.remove_tag("gcse")
    assert tag_filter.chosen() == []
    assert tree_files(window) == set(FILES)
    assert "gcse" not in [c.tag for c in tag_filter.counts()]


def test_the_resources_folder_is_not_written(window: MainWindow, fake_root: Path) -> None:
    before = {p: p.read_bytes() for p in fake_root.rglob("*") if p.is_file()}
    window.resources.tag_filter.toggle_tag("loops")
    window.resources.search.setText("FAKE")
    window.resources.tag_filter.clear()
    after = {p: p.read_bytes() for p in fake_root.rglob("*") if p.is_file()}
    assert after == before


def test_button_without_tags(qtbot: QtBot) -> None:
    button = TagFilterButton()
    qtbot.addWidget(button)
    assert button.tag_actions() == []
    assert [a.text() for a in button.menu_.actions()] == [EMPTY_HINT]
    seen: list[list[str]] = []
    button.tags_changed.connect(seen.append)
    button.set_counts([TagCount("loops", 1)])
    button.toggle_tag("loops")
    button.set_chosen(["loops"])  # no change, no signal
    assert seen == [["loops"]]


def test_button_text_cuts_a_long_tag() -> None:
    assert button_text([]) == "Tags ▾"
    assert button_text(["computational-thinking", "ks3"]) == "computation… +1 ▾"
