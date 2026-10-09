"""The library picker palette: tree when empty, rich results when typing,
filter by extension, keyboard choose, and the picker widget's display."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from staffroom.core.library.service import LibraryService
from staffroom.core.panel import ResourcePicker
from staffroom.shell.library.picker import REL_ROLE, ResourcePickerDialog
from staffroom.shell.widgets import ResourcePickerWidget


def test_tree_then_results(qtbot: QtBot, service: LibraryService, resources_root: Path) -> None:
    dialog = ResourcePickerDialog(service, None, None)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.stack.currentWidget() is dialog.tree
    assert dialog.tree_model.rowCount() >= 2
    assert not dialog.choose_button.isEnabled()

    dialog.search.setText("while")
    assert dialog.stack.currentWidget() is dialog.results
    # item(i) wrappers are dropped with each comprehension; the list is not cleared meanwhile (#54).
    rels = [dialog.results.item(i).data(REL_ROLE) for i in range(dialog.results.count())]
    assert "Python/Python_Course/while_loops.py" in rels
    assert "Python/Python_Course/while_loops.pptx" in rels  # by name
    assert "Python/cloud_file.py" not in rels  # cloud-only never offered
    assert dialog.choose_button.isEnabled()  # first result preselected
    assert dialog.selected_label.text() == rels[0]

    qtbot.keyClick(dialog.search, Qt.Key.Key_Down)
    assert dialog.selected_label.text() == rels[1]
    with qtbot.waitSignal(dialog.accepted, timeout=1000):
        qtbot.keyClick(dialog.search, Qt.Key.Key_Return)
    assert dialog.chosen() == resources_root / rels[1]


def test_filter_ext_and_name_fallback(qtbot: QtBot, service: LibraryService) -> None:
    dialog = ResourcePickerDialog(service, ".py", None)
    qtbot.addWidget(dialog)
    dialog.search.setText("while")
    rels = [dialog.results.item(i).data(REL_ROLE) for i in range(dialog.results.count())]
    assert rels and all(r.endswith(".py") for r in rels)
    dialog.search.setText("3a")  # substring of a name, not a word FTS would find
    rels = [dialog.results.item(i).data(REL_ROLE) for i in range(dialog.results.count())]
    assert "Python/OCR Booklet/exercise_3a.py" in rels
    dialog.search.setText("zzzz")
    assert dialog.results.item(0).text() == "No matches" and not dialog.choose_button.isEnabled()


def test_picker_widget_shows_relative_path(
    qtbot: QtBot, service: LibraryService, resources_root: Path, tmp_path: Path
) -> None:
    widget = ResourcePickerWidget(ResourcePicker(key="r", label="Resource"), service)
    qtbot.addWidget(widget)
    inside = resources_root / "Python" / "notes.md"
    widget.set_path(inside)
    assert widget.edit.text() == "Python/notes.md"
    assert widget.value() == inside
    outside = tmp_path / "elsewhere.py"
    widget.set_path(outside)
    assert widget.edit.text() == str(outside)
    assert widget.value() == outside
    widget.edit.setText("Python/readme.txt")  # typed relative path resolves against the root
    assert widget.value() == resources_root / "Python" / "readme.txt"
