"""One code source for the code tools (#86): a chip over a numbered,
highlighted view of the program; *Paste instead* for code in no file; trace
rows and program lines lit both ways; pseudocode's From follows the code
(#62)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QPushButton
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.panel import CodeValue
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets import CodeSourceWidget, CodeViewWidget

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
CODE_TOOLS = ("parsons", "trace", "bugs", "fade", "pseudocode")


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False)
    qtbot.addWidget(win)
    win.resize(1240, 780)
    win.show()
    return win


def _panel(window: MainWindow, name: str) -> ToolPanel:
    window.sidebar.select(name)
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == name
    return panel


def _run(panel: ToolPanel, qtbot: QtBot) -> None:
    with qtbot.waitSignal(panel.run_finished, timeout=60000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.strip.text()


@pytest.mark.parametrize("name", CODE_TOOLS)
def test_one_code_input_replaces_file_and_paste(window: MainWindow, name: str) -> None:
    panel = _panel(window, name)
    assert list(panel.code_sources) == ["source"]
    assert "pasted" not in panel.text_areas and not panel.resource_pickers
    code = panel.code_sources["source"]
    assert code.mode_link.text() == "Paste instead"
    assert code.view.isReadOnly()


def test_picking_a_file_fills_the_view(window: MainWindow) -> None:
    panel = _panel(window, "trace")
    code = panel.code_sources["source"]
    program = EXAMPLES / "year9.py"
    panel.set_input_path("source", program)
    text = program.read_text(encoding="utf-8")
    assert code.view.toPlainText() == text.rstrip("\n")
    # Numbered the way the sheets number it: one line per line of the file.
    assert code.view.line_count() == len(text.rstrip("\n").splitlines())
    assert code.view.isReadOnly() and code.name.text() == "year9.py"
    assert code.value() == CodeValue(program, text.rstrip("\n"))
    assert code.change.isVisible() and not code.browse_button.isVisible()


def test_paste_overrides_the_file_and_goes_back(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    panel = _panel(window, "fade")
    code = panel.code_sources["source"]
    panel.set_input_path("source", EXAMPLES / "year9.py")
    code.mode_link.click()  # Paste instead: an empty, editable view
    assert code.pasting and not code.view.isReadOnly() and code.view.toPlainText() == ""
    assert code.mode_link.text() == "Use a file"
    code.view.setPlainText("x = 1\ny = 2\nprint(x + y)\n")
    assert panel.collect_inputs()["source"] == CodeValue(None, "x = 1\ny = 2\nprint(x + y)\n")
    _run(panel, qtbot)
    assert (tmp_path / "out" / "pasted_code_faded_key.docx").exists()
    code.mode_link.click()  # Use a file: back to the file, read-only again
    assert not code.pasting and code.view.isReadOnly()
    assert code.value().path == EXAMPLES / "year9.py"
    code.mode_link.click()  # and the paste is still there
    assert code.view.toPlainText().startswith("x = 1")


def test_a_file_saved_again_is_shown_again(window: MainWindow, tmp_path: Path) -> None:
    program = tmp_path / "loop.py"
    program.write_text("for i in range(3):\n    print(i)\n", encoding="utf-8")
    panel = _panel(window, "parsons")
    panel.set_input_path("source", program)
    program.write_text("total = 0\nfor i in range(3):\n    total += i\n", encoding="utf-8")
    panel.code_sources["source"].reload()  # what a run does first
    assert panel.code_sources["source"].view.toPlainText().startswith("total = 0")


def test_not_an_editor(window: MainWindow) -> None:
    """Thonny is the editor: no save, no run, nothing but the chip's choices
    and the paste link."""
    code = _panel(window, "trace").code_sources["source"]
    labels = {b.text() for b in code.findChildren(QPushButton)} | {code.mode_link.text()}
    assert labels == {"From library…", "Browse…", "Change ▾", "Paste instead"}


def _click_line(view: CodeViewWidget, qtbot: QtBot, line: int) -> None:
    block = view.document().findBlockByNumber(line - 1)
    view.centerCursor()
    rect = view.blockBoundingGeometry(block).translated(view.contentOffset())
    point = QPoint(40, int(rect.center().y()))
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)


def test_trace_rows_and_lines_light_each_other(window: MainWindow, qtbot: QtBot) -> None:
    panel = _panel(window, "trace")
    panel.set_input_path("source", EXAMPLES / "year9.py")
    _run(panel, qtbot)
    model, table, _caption = panel.results.tables["table"]
    view = panel.code_sources["source"].view
    line_col = next(
        c
        for c in range(model.columnCount())
        if model.headerData(c, Qt.Orientation.Horizontal) == "Line"
    )

    # A row lights its line.
    table.selectRow(4)
    row_line = int(model.index(4, line_col).data())
    assert view.lit_lines() == [row_line]
    source_line = view.document().findBlockByNumber(row_line - 1).text()
    assert source_line.strip()  # a real line of the program, not a blank one

    # A line selects every row that points at it.
    loop_line = int(model.index(model.rowCount() - 1, line_col).data())
    _click_line(view, qtbot, loop_line)
    rows = sorted({i.row() for i in table.selectionModel().selectedIndexes()})
    expected = [
        r for r in range(model.rowCount()) if int(model.index(r, line_col).data()) == loop_line
    ]
    assert rows == expected and len(rows) >= 1
    assert view.lit_lines() == [loop_line]

    # A new run starts with nothing lit.
    _run(panel, qtbot)
    assert view.lit_lines() == []


def test_bugs_key_cards_point_at_lines(window: MainWindow, qtbot: QtBot) -> None:
    panel = _panel(window, "bugs")
    panel.set_input_path("source", EXAMPLES / "year9.py")
    _run(panel, qtbot)
    cards = panel.results.card_lists["key"]
    cards.selectRow(0)
    line = int(cards.model().index(0, 1).data())  # Version, Line, …
    assert panel.code_sources["source"].view.lit_lines() == [line]


def test_pseudocode_source_beside_translation(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    panel = _panel(window, "pseudocode")
    code = panel.code_sources["source"]
    assert panel.choices["from"].value() == "guess"  # nothing chosen yet
    panel.set_input_path("source", EXAMPLES / "year9.py")
    assert panel.choices["from"].value() == "python"  # #62: From follows the file
    _run(panel, qtbot)
    out = panel.results.text_views["output"]
    assert isinstance(out, CodeViewWidget) and "next" in out.toPlainText()
    # Source left, translation right, notes under the translation, all in view.
    left = code.view.mapTo(window, QPoint(0, 0))
    right = out.mapTo(window, QPoint(0, 0))
    assert left.x() + code.view.width() <= right.x()
    report = panel.results.sections["report"]
    assert report.isVisible()
    assert report.mapTo(window, QPoint(0, report.height())).y() <= window.height()

    # An OCR ERL file: From follows it, and To moves off OCR ERL.
    ocr = tmp_path / "loop.txt"
    ocr.write_text("for i = 0 to 2\n    print(i)\nnext i\n", encoding="utf-8")
    assert panel.choices["to"].value() == "ocr"
    panel.set_input_path("source", ocr)
    assert panel.choices["from"].value() == "ocr" and panel.choices["to"].value() == "python"
    _run(panel, qtbot)
    assert "for i in range" in panel.results.text_views["output"].toPlainText()

    # Pasted code is guessed too; nothing to go on goes back to Guess.
    panel.set_text("source", "x ← 5\nOUTPUT x\n")
    assert panel.choices["from"].value() == "aqa"
    panel.set_text("source", "")
    assert panel.choices["from"].value() == "guess"


def test_code_source_widget_alone(qtbot: QtBot, tmp_path: Path) -> None:
    from staffroom.core.panel import CodeSource

    widget = CodeSourceWidget(CodeSource(key="source"), None)
    qtbot.addWidget(widget)
    assert widget.value() == CodeValue(None, "")
    assert not widget.library_button.isEnabled()  # no library: Browse only
    missing = tmp_path / "gone.py"
    widget.set_path(missing)
    assert widget.view.toPlainText() == "" and "Could not find gone.py" in (
        widget.view.placeholderText()
    )
