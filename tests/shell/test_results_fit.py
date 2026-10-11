"""Results that fit (#16): the trace table and the bugs key show what was
printed and what each bug does without sideways scrolling.

The probe is the 2026-10-11 audit's (§1b R2) turned into a test: run trace
and bugs on ``examples/year9.py`` in a window of the given size and ask which
columns, and which outcomes, are fully inside the output pane. Before #16, at
1040x680, trace showed 3 of 7 columns (no Output) and bugs 3 of 6 (no
outcome)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from staffroom.core import paths
from staffroom.core.config import load_config
from staffroom.core.panel import CardList, ResultsTable
from staffroom.core.plugin import RunResult
from staffroom.core.table import Table
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets import CodeViewWidget, OutputPane
from staffroom.shell.widgets.table_view import CHANGE_ROLE

EXAMPLES = paths.examples_dir()
SIZES = [(1240, 780), (1040, 680)]


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False, first_run=False)
    qtbot.addWidget(win)
    win.show()
    return win


def run_on_year9(window: MainWindow, qtbot: QtBot, name: str, size: tuple[int, int]) -> ToolPanel:
    window.resize(*size)
    window.go_to_tool(name)
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == name
    panel.set_input_path("source", EXAMPLES / "year9.py")
    with qtbot.waitSignal(panel.run_finished, timeout=60000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.strip.text()
    QApplication.processEvents()
    return panel


def click_line(view: CodeViewWidget, qtbot: QtBot, line: int) -> None:
    block = view.document().findBlockByNumber(line - 1)
    rect = view.blockBoundingGeometry(block).translated(view.contentOffset())
    point = QPoint(40, int(rect.center().y()))
    qtbot.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)


# ---------------------------------------------------------------- the probe
@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_trace_shows_every_column_and_output_without_scrolling(
    window: MainWindow, qtbot: QtBot, size: tuple[int, int]
) -> None:
    panel = run_on_year9(window, qtbot, "trace", size)
    fit = panel.results.fit_tables["table"]
    model = fit.model
    assert model.columnCount() == 7  # the tool's table is whole: the printed key's columns
    shown = fit.visible_columns()
    assert shown[-1] == "Output"  # pinned: the last column on screen
    assert fit.lifted_names() == ["scores"]
    assert sorted([*shown, *fit.lifted_names()]) == sorted(model.table().columns)
    assert fit.view.horizontalScrollBar().maximum() == 0  # nothing to scroll to
    assert fit.lifted_text() == "Never changes after line 2: scores = [45, 62, 58, 71, 39]"


@pytest.mark.parametrize("size", SIZES, ids=lambda s: f"{s[0]}x{s[1]}")
def test_bugs_shows_every_outcome_without_scrolling(
    window: MainWindow, qtbot: QtBot, size: tuple[int, int]
) -> None:
    panel = run_on_year9(window, qtbot, "bugs", size)
    cards = panel.results.card_lists["key"]
    assert cards.count() == 4
    assert cards.visible_badges() == cards.count()
    outcomes = [str(r[5]) for r in cards.model().table().rows]
    assert [c.badge.text() for c in cards.cards if c.badge] == outcomes
    assert cards.horizontalScrollBar().maximum() == 0


# ---------------------------------------------------------------- trace's table
def test_trace_marks_changes_and_keeps_lines_linked_both_ways(
    window: MainWindow, qtbot: QtBot
) -> None:
    panel = run_on_year9(window, qtbot, "trace", (1040, 680))
    fit = panel.results.fit_tables["table"]
    model, view = fit.model, fit.view
    columns = model.table().columns
    total = columns.index("total")
    # Row 2 is line 3, `total = 0`: set there (bold); row 3 carries it (grey).
    assert model.index(1, total).data(CHANGE_ROLE) is True
    assert model.index(2, total).data(CHANGE_ROLE) is False
    assert model.index(1, 0).data(CHANGE_ROLE) is None  # the line column stays plain
    assert view.isColumnHidden(columns.index("scores"))  # lifted
    assert view.isColumnHidden(columns.index("Output"))  # shown in the pinned view
    assert "bold: changed on this line" in fit.caption.text()

    code = panel.code_sources["source"].view
    # Keyboard: the arrow keys move the row and the lit line follows.
    view.setFocus()
    view.selectRow(4)
    qtbot.keyClick(view, Qt.Key.Key_Down)
    assert code.lit_lines() == [int(model.index(5, 0).data())]
    # A click on the pinned column selects that row in both views.
    assert fit.pinned is not None
    pinned_cell = fit.pinned.visualRect(model.index(2, len(columns) - 1)).center()
    qtbot.mouseClick(fit.pinned.viewport(), Qt.MouseButton.LeftButton, pos=pinned_cell)
    assert sorted({i.row() for i in view.selectionModel().selectedIndexes()}) == [2]
    assert code.lit_lines() == [int(model.index(2, 0).data())]
    # A line selects its rows.
    click_line(code, qtbot, 7)
    rows = sorted({i.row() for i in view.selectionModel().selectedIndexes()})
    assert rows and all(int(model.index(r, 0).data()) == 7 for r in rows)


# ---------------------------------------------------------------- bugs' cards
def test_bugs_cards_light_lines_both_ways_and_follow_the_keys(
    window: MainWindow, qtbot: QtBot
) -> None:
    panel = run_on_year9(window, qtbot, "bugs", (1040, 680))
    cards = panel.results.card_lists["key"]
    code = panel.code_sources["source"].view
    lines = [int(r[1]) for r in cards.model().table().rows]
    first = cards.cards[0]
    assert first.title.text() == "Version 1"
    assert first.details[0].text() == f"line {lines[0]}"
    assert [c.text() for c in first.code] == [str(v) for v in cards.model().table().rows[0][3:5]]

    # A click on a card lights its line and rings the card.
    qtbot.mouseClick(cards.cards[1], Qt.MouseButton.LeftButton, pos=QPoint(20, 10))
    assert cards.selected_rows() == [1] and code.lit_lines() == [lines[1]]
    assert cards.cards[1].property("selected") and not cards.cards[0].property("selected")
    # Keyboard: Down, End, Home move the selection; the line follows.
    qtbot.keyClick(cards, Qt.Key.Key_Down)
    assert cards.selected_rows() == [2] and code.lit_lines() == [lines[2]]
    qtbot.keyClick(cards, Qt.Key.Key_End)
    assert cards.selected_rows() == [3]
    qtbot.keyClick(cards, Qt.Key.Key_Home)
    assert cards.selected_rows() == [0] and code.lit_lines() == [lines[0]]
    # A line in the program selects the cards that broke it.
    click_line(code, qtbot, lines[2])
    assert cards.selected_rows() == [r for r, n in enumerate(lines) if n == lines[2]]
    # A new run starts with nothing lit.
    with qtbot.waitSignal(panel.run_finished, timeout=60000):
        panel.start_run()
    assert code.lit_lines() == [] and cards.selected_rows() == []


# ---------------------------------------------------------------- any tool can use them
def test_card_list_is_a_kit_output(qtbot: QtBot) -> None:
    spec = CardList(
        "items",
        label="Items",
        title="Item {N}",
        details=("{Kind}",),
        badge="Result",
        tone_column="Tone",
        tones=(("bad", "danger"), ("meh", "warning")),
        code_lines=(("was", "Old"), ("now", "New")),
    )
    pane = OutputPane((spec,))
    qtbot.addWidget(pane)
    pane.resize(420, 500)
    pane.show()
    # FAKE DATA: invented rows.
    table = Table(
        ["N", "Kind", "Result", "Tone", "Old", "New"],
        [
            [
                1,
                "a very long kind of thing that has to wrap onto a second line",
                "breaks",
                "bad",
                "x = 1",
                "x = 2",
            ],
            [2, "", "goes wrong quietly", "meh", "    y", "y"],
            [3, "plain", "same", "other", "z", "z"],
        ],
    )
    pane.apply(RunResult(tables={"items": table}))
    QApplication.processEvents()
    cards = pane.card_lists["items"]
    assert [c.badge.property("tone") for c in cards.cards if c.badge] == [
        "danger",
        "warning",
        "neutral",
    ]
    assert cards.cards[1].details == []  # a blank detail is left out
    assert cards.cards[1].code[0].text() == "    y"  # indentation kept
    assert cards.visible_badges() == 3  # the long detail wraps; no badge is cut
    pane.clear()
    assert cards.count() == 0


def test_a_fitted_table_pins_its_last_column_in_a_narrow_pane(qtbot: QtBot) -> None:
    spec = ResultsTable("t", compact=True, lift_constants=True, mark_changes=True, pin_last=True)
    pane = OutputPane((spec,))
    qtbot.addWidget(pane)
    pane.resize(360, 500)
    pane.show()
    # FAKE DATA: ten wide invented columns, a constant, and a last column to keep.
    columns = [f"column_{i}" for i in range(10)]
    rows = [[f"value {r}-{c}" for c in range(9)] + [f"out {r}"] for r in range(5)]
    for row in rows:
        row[3] = "same every time"
    pane.apply(RunResult(tables={"t": Table(columns, rows)}))
    QApplication.processEvents()
    fit = pane.fit_tables["t"]
    assert fit.lifted_names() == ["column_3"]
    assert fit.visible_columns()[-1] == "column_9"  # the pinned column is in view
    assert fit.view.horizontalScrollBar().maximum() > 0  # the rest scroll under it
    pinned = fit.pinned
    assert pinned is not None
    right = pinned.mapTo(fit.frame, QPoint(pinned.width(), 0)).x()
    assert fit.frame.width() - right <= 3  # at the right edge, inside the frame's border
