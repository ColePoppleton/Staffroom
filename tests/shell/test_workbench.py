"""The workbench layout (#83): inputs pane on the left with the run button at
its foot, output pane on the right, and the first result in view after a run.

The probe is the audit's (docs/audits/2026-10-09.md §1) turned into a test: at
1240x780 offscreen, run each of the nine tools and measure where its first
result sits. Before #83 it was below the fold in 7 of 9 tools."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from staffroom.core import launch, paths
from staffroom.core.config import load_config
from staffroom.core.panel import (
    ActionTable,
    BarChart,
    ImageView,
    LogArea,
    ResultsTable,
    StatTiles,
    TablePreview,
    TextView,
    below_outputs,
    main_outputs,
    top_outputs,
)
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import INPUTS_MIN_WIDTH, INPUTS_WIDTH, ToolPanel
from staffroom.shell.widgets import InputGroup

EXAMPLES = paths.examples_dir()
# What each tool is run on: the file for its first file input (None: no file).
RUNS: dict[str, Path | None] = {
    "classroom": EXAMPLES / "year9.py",
    "marks": EXAMPLES / "marks_10x_max.csv",
    "worksheet": None,
    "parsons": EXAMPLES / "year9.py",
    "quiz": EXAMPLES / "question_bank.md",
    "trace": EXAMPLES / "year9.py",
    "bugs": EXAMPLES / "year9.py",
    "fade": EXAMPLES / "year9.py",
    "pseudocode": EXAMPLES / "year9.py",
}
MIN_VISIBLE = 200  # px of the first result that must show without scrolling


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    monkeypatch.setattr(launch, "_popen", lambda argv: None)  # classroom opens an editor
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    config.general.sessions_root = str(tmp_path / "sessions")
    win = MainWindow(config, auto_index=False, first_run=False)
    qtbot.addWidget(win)
    win.resize(1240, 780)
    win.show()
    return win


def open_tool(window: MainWindow, name: str) -> ToolPanel:
    window.go_to_tool(name)
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == name
    QApplication.processEvents()
    return panel


def run(panel: ToolPanel, qtbot: QtBot) -> None:
    path = RUNS[panel.plugin.name]
    key = panel.first_file_key()
    if path is not None and key is not None:
        panel.set_input_path(key, path)
    if "label" in panel.text_fields:
        panel.set_text("label", "P3 loops")
    with qtbot.waitSignal(panel.run_finished, timeout=60000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.run_bar.status.text()
    QApplication.processEvents()


def first_result(panel: ToolPanel) -> QWidget:
    """The widget showing the panel's first main output."""
    pane = panel.results
    key = pane.main_keys[0]
    if key in pane.tables:
        return pane.tables[key][1]
    if key in pane.images:
        return pane.images[key]
    if key in pane.text_views:
        return pane.text_views[key]
    if key in pane.charts:
        return pane.charts[key]
    return pane.action_tables[key]


def measure(window: MainWindow, panel: ToolPanel) -> tuple[int, int]:
    """(top y in the window, visible height) of the first result."""
    widget = first_result(panel)
    top = widget.mapTo(window, QPoint(0, 0)).y()
    visible = widget.visibleRegion().boundingRect().height() if widget.isVisible() else 0
    return top, visible


# ---------------------------------------------------------------- placement (core)
def test_placement_defaults_and_hints() -> None:
    outputs = (
        ActionTable("sessions", "Sessions", actions=()),
        ResultsTable("table"),
        TextView("notes", place="below"),
        ImageView("chart"),
        LogArea(),
    )
    assert [w.key for w in main_outputs(outputs)] == ["table", "chart"]
    assert [w.key for w in below_outputs(outputs)] == ["sessions", "notes"]


def test_headline_tiles_sit_on_top_and_never_become_a_tab() -> None:
    outputs = (
        StatTiles("headline"),
        BarChart("chart"),
        ResultsTable("table"),
        ResultsTable("detail", place="below", collapsed=True),
        LogArea(),
    )
    assert [w.key for w in top_outputs(outputs)] == ["headline"]
    assert [w.key for w in main_outputs(outputs)] == ["chart", "table"]
    assert [w.key for w in below_outputs(outputs)] == ["detail"]
    # Only tiles: they are the headline, and nothing is promoted into the main view.
    assert main_outputs((StatTiles("headline"),)) == []


def test_a_panel_of_only_secondary_outputs_promotes_the_first() -> None:
    outputs = (ActionTable("sessions", "Sessions", actions=()), LogArea())
    assert [w.key for w in main_outputs(outputs)] == ["sessions"]
    assert below_outputs(outputs) == []
    assert main_outputs((LogArea(),)) == []


# ---------------------------------------------------------------- the layout
def test_every_panel_is_inputs_pane_plus_output_pane(window: MainWindow) -> None:
    assert len(window.visible_plugins) == len(RUNS)
    for plugin in window.visible_plugins:
        panel = open_tool(window, plugin.name)
        assert panel.inputs_pane.width() == INPUTS_WIDTH, plugin.name
        assert panel.inputs_pane.isAncestorOf(panel.run_bar)  # the action at its foot
        left = panel.inputs_pane.mapTo(panel, QPoint(0, 0)).x()
        right = panel.results.mapTo(panel, QPoint(0, 0)).x()
        assert left < right, plugin.name
        # One hairline group per input (a compact preview joins its file's group);
        # no Card per input.
        groups = panel.inputs_pane.findChildren(InputGroup)
        own = [w for w in panel.spec.inputs if not (isinstance(w, TablePreview) and w.compact)]
        assert len(groups) == len(own), plugin.name
        assert not panel.inputs_pane.findChildren(QWidget, "Card")
        # A tab per main output, in spec order; or a titled card each in a row.
        main = [w.label for w in main_outputs(panel.spec.outputs)]
        if panel.spec.main_layout == "row":
            assert panel.results.tabs is None, plugin.name
            assert [c.title.text() for c in panel.results.cards.values()] == main
        else:
            tabs = panel.results.tabs
            assert tabs is not None
            assert [tabs.tabText(i) for i in range(tabs.count())] == main, plugin.name


def test_first_result_is_visible_after_a_run_in_every_tool(
    window: MainWindow, qtbot: QtBot
) -> None:
    """The audit's probe: 2/9 before the workbench, 9/9 now."""
    height = window.height()
    report: dict[str, tuple[int, int, int]] = {}
    for plugin in window.visible_plugins:
        panel = open_tool(window, plugin.name)
        run(panel, qtbot)
        top, visible = measure(window, panel)
        # In view: the whole result (a one-row list is short), or a good part of it.
        report[plugin.name] = (top, visible, first_result(panel).height())
        # Nothing scrolled on its own: both panes are where the teacher left them.
        assert panel.results.scroll_area.verticalScrollBar().value() == 0
        assert panel.inputs_scroll.verticalScrollBar().value() == 0
        # The inputs are still on screen beside the result.
        assert panel.run_bar.button.visibleRegion().boundingRect().height() > 0
    in_view = {
        name
        for name, (top, visible, full) in report.items()
        if top < height and visible >= min(MIN_VISIBLE, full)
    }
    assert in_view == set(RUNS), f"first result (top y, visible px, height): {report}"


def test_window_minimum_still_fits_both_panes(window: MainWindow) -> None:
    window.resize(1040, 680)
    room = 1040 - window.sidebar.width()
    for plugin in window.visible_plugins:
        panel = open_tool(window, plugin.name)
        hint = panel.minimumSizeHint()
        assert hint.width() <= room and hint.height() <= 680, (plugin.name, hint)
        assert INPUTS_MIN_WIDTH <= panel.inputs_pane.width() < INPUTS_WIDTH, plugin.name
        # Neither pane is wider than the space it has: nothing clipped sideways.
        body = panel.inputs_scroll.widget()
        assert body is not None
        assert body.minimumSizeHint().width() <= panel.inputs_scroll.viewport().width(), plugin.name
        assert panel.results.minimumSizeHint().width() <= panel.results.width(), plugin.name
        assert panel.inputs_pane.width() + panel.results.width() <= panel.width()
        assert panel.run_bar.button.visibleRegion().boundingRect().width() > 0


def test_inputs_fit_the_pane_at_full_width(window: MainWindow) -> None:
    for plugin in window.visible_plugins:
        panel = open_tool(window, plugin.name)
        body = panel.inputs_scroll.widget()
        assert body is not None
        assert body.minimumSizeHint().width() <= panel.inputs_scroll.viewport().width(), plugin.name


# ---------------------------------------------------------------- behaviour
def test_cmd_return_runs_the_visible_tool_only(window: MainWindow, qtbot: QtBot) -> None:
    trace = open_tool(window, "trace")
    trace.set_input_path("source", EXAMPLES / "year9.py")
    worksheet = open_tool(window, "worksheet")
    window.activateWindow()
    qtbot.waitUntil(lambda: QApplication.activeWindow() is window)
    with qtbot.waitSignal(worksheet.run_finished, timeout=60000) as blocker:
        qtbot.keyClick(worksheet, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert blocker.args == [True]
    assert trace.worker is None  # the hidden panel's shortcut did not fire


def test_marks_keeps_the_view_only_label_below_the_main_view(
    window: MainWindow, qtbot: QtBot
) -> None:
    panel = open_tool(window, "marks")
    grades = next(w for w in below_outputs(panel.spec.outputs) if w.key == "grades")
    assert grades.label == "Per-script grades (view only, never saved)"
    assert isinstance(grades, ResultsTable) and grades.collapsed
    section = panel.results.sections["grades"]
    assert not section.isVisible()  # nothing to show before a run
    run(panel, qtbot)
    assert section.isVisible()
    assert panel.results.folds["grades"].toolTip() == grades.label
    assert panel.results.is_folded("grades")  # one click away, not in the way


def test_output_pane_waits_with_a_hint_then_shows_the_result(
    window: MainWindow, qtbot: QtBot
) -> None:
    panel = open_tool(window, "worksheet")
    view = first_result(panel)
    assert not view.isVisible()  # the hint shows until there is something
    assert panel.results.empty_text.startswith("Press Make worksheet")
    run(panel, qtbot)
    assert view.isVisible()
    assert panel.results.strip_slot.count() == 0  # the top edge is free for #84


def test_classroom_lists_sessions_first_and_the_diff_below(window: MainWindow) -> None:
    panel = open_tool(window, "classroom")
    assert panel.results.main_keys == ["sessions"]
    assert [w.key for w in below_outputs(panel.spec.outputs)] == ["diff"]
    assert panel.run_bar.folder.text().startswith("Copies to ")
