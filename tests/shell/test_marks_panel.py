"""The marks panel as a report (#87): the file as a chip with what was found,
boundaries as a compact grid with a % / raw switch, and after Analyse four
headline tiles, the grade chart beside one per-question table (hardest first,
reteach marked) and the per-script grades folded away, on screen only.

The hard rule stays tested here as well as in the tool's own tests: a run
from the panel writes the two aggregate CSVs and the chart, nothing per
script."""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.csvio import read_table
from staffroom.core.table import Table
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets import CompactTableWidget, TablePreviewWidget
from staffroom.tools.marks.panel import GRADES_LABEL


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False, first_run=False)
    qtbot.addWidget(win)
    win.resize(1240, 780)
    win.show()
    win.sidebar.select("marks")
    return win


def marks_panel(window: MainWindow) -> ToolPanel:
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == "marks"
    return panel


def analyse(panel: ToolPanel, qtbot: QtBot, source: Path) -> None:
    panel.set_input_path("marks", source)
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.run_bar.status.text()
    QApplication.processEvents()


# ---------------------------------------------------------------- inputs
def test_boundaries_are_a_compact_grid_with_presets(window: MainWindow) -> None:
    panel = marks_panel(window)
    grid = panel.grids["boundaries"]
    assert isinstance(grid, CompactTableWidget)
    assert len(grid.cells) == 10 and grid.preset_combo.currentText() == "OCR J277 (GCSE 9-1)"
    assert [c.label.text() for c in grid.cells[:5]] == ["9", "8", "7", "6", "5"]
    # Two lines of five: the whole grid is visible without scrolling inside it.
    assert grid.grid.rowCount() == 2
    grid.preset_combo.setCurrentText("A-level (A*-E)")  # choosing applies at once
    assert grid.model.rowCount() == 7 and grid.value().rows[0][0] == "A*"
    grid.cells[0].edit.setText("85")
    grid.cells[0].edit.textEdited.emit("85")
    assert grid.value().rows[0] == ["A*", 85.0]


def test_save_preset_from_the_grid(window: MainWindow) -> None:
    panel = marks_panel(window)
    grid = panel.grids["boundaries"]
    assert isinstance(grid, CompactTableWidget)
    assert panel.groups["boundaries"].trailing.indexOf(grid.save_button) >= 0  # in the heading
    grid.add_preset("Custom A", grid.value().rows)
    grid.preset_saved.emit("Custom A", grid.value())
    assert "Custom A" in load_config().tool("marks")["presets"]
    assert "Saved preset" in panel.strip.text()


def test_file_chip_and_load_summary_instead_of_a_preview_table(
    window: MainWindow, example_marks_max: Path
) -> None:
    panel = marks_panel(window)
    assert not panel.previews  # no eleven-row table in the inputs pane
    picker = panel.pickers["marks"]
    assert picker.chip is not None and not picker.chip.isVisible()
    picker.set_path(example_marks_max)
    assert picker.chip.isVisible() and picker.name.text() == "marks_10x_max.csv"
    assert picker.badge.text() == "CSV"
    summary = panel.summaries["preview"]
    texts = [n.text for n in summary.notes()]
    assert texts == [
        "10 scripts × 6 questions · MAX row found (paper out of 40)",
        "No identifier columns · ignored: row",
    ]
    assert all(n.ok for n in summary.notes())
    # The rows are a click away, the MAX row included, never in the pane itself.
    summary.preview_button.click()
    assert isinstance(summary.dialog, QDialog)
    preview = summary.dialog.findChild(TablePreviewWidget)
    assert preview is not None and preview.model.rowCount() == 11
    summary.dialog.close()


def test_load_summary_names_dropped_identifier_columns(window: MainWindow, tmp_path: Path) -> None:
    src = tmp_path / "with_names.csv"
    src.write_text("# FAKE DATA\nName,q1,q2\nMAX,4,6\nx,3,5\ny,4,6\n")
    panel = marks_panel(window)
    panel.set_input_path("marks", src)
    notes = panel.summaries["preview"].notes()
    # The MAX word was in the dropped column: the flag still finds the row.
    assert notes[0].text == "2 scripts × 2 questions · MAX row found (paper out of 10)"
    assert notes[1].text == "Identifier column dropped, never used: Name"


# ---------------------------------------------------------------- the report
def test_report_after_analyse(window: MainWindow, qtbot: QtBot, example_marks_max: Path) -> None:
    panel = marks_panel(window)
    analyse(panel, qtbot, example_marks_max)
    pane = panel.results
    # Headline: the numbers worked out by hand in the tool's test_logic.py.
    assert pane.tiles["headline"].values() == {
        "Scripts": "10",
        "Mean": "75%",
        "Median grade": "8",
        "Reteach first": "q6, q3, q4",
    }
    # The chart: one bar per grade, counts and % under them; the table behind a switch.
    chart = pane.charts["distribution"]
    assert [(b.category, b.value, b.detail) for b in chart.canvas.bars][:3] == [
        ("9", 4.0, "40%"),
        ("8", 3.0, "30%"),
        ("7", 0.0, "0%"),
    ]
    assert len(chart.canvas.bars) == 10
    assert pane.cards["distribution"].caption.text() == "OCR J277 · %"
    chart.toggle.click()
    assert chart.showing_table() and chart.model.rowCount() == 10
    # One question table, hardest first, reteach marked; no separate "worst" view.
    model, view, _caption = pane.tables["questions"]
    assert [model.index(r, 0).data() for r in range(6)] == ["q6", "q3", "q4", "q5", "q2", "q1"]
    assert [model.tag(r) for r in range(6)] == ["reteach"] * 3 + [""] * 3
    assert "worst" not in pane.tables and "worst" not in pane.sections
    assert view.isColumnHidden(model._table.columns.index("Reteach"))
    # Chart and table side by side at 1240 x 780, not stacked.
    assert pane.row is not None and not pane.row.stacked()


def test_per_script_grades_are_folded_view_only_and_never_saved(
    window: MainWindow, qtbot: QtBot, example_marks_max: Path, tmp_path: Path
) -> None:
    panel = marks_panel(window)
    pane = panel.results
    assert not pane.sections["grades"].isVisible()  # nothing before a run
    analyse(panel, qtbot, example_marks_max)
    fold = pane.folds["grades"]
    assert pane.sections["grades"].isVisible() and pane.is_folded("grades")
    assert GRADES_LABEL == "Per-script grades (view only, never saved)"
    assert fold.text() == f"▸ {GRADES_LABEL} · 10 rows"
    fold.click()
    assert not pane.is_folded("grades") and pane.tables["grades"][0].rowCount() == 10
    # On disk: the two aggregate CSVs and the chart, nothing per script.
    out = tmp_path / "out"
    assert sorted(p.name for p in out.iterdir()) == [
        "marks_10x_max_distribution.csv",
        "marks_10x_max_distribution.png",
        "marks_10x_max_questions.csv",
    ]
    for p in out.glob("*.csv"):
        saved = read_table(p)
        assert "Total" not in saved.columns and "Percent" not in saved.columns[:1]
        assert not any(c.lower().startswith("q") and c != "Question" for c in saved.columns)
        assert len(saved) <= 11  # one row per grade or per question, never per script
    questions = read_table(out / "marks_10x_max_questions.csv")
    assert questions.column("Question") == ["q1", "q2", "q3", "q4", "q5", "q6"]  # paper order
    assert questions.columns == ["Question", "Max", "Mean", "Facility", "Discrimination", "Note"]


def test_unit_switch_reaches_the_run(
    window: MainWindow, qtbot: QtBot, example_marks_max: Path
) -> None:
    panel = marks_panel(window)
    panel.choices["unit"].set_value("raw")
    assert panel.collect_inputs()["unit"] == "raw"
    analyse(panel, qtbot, example_marks_max)
    log = panel.results.log_view
    assert log is not None and "above the paper total of 40" in log.toPlainText()
    assert panel.results.cards["distribution"].caption.text() == "OCR J277 · raw"


# ---------------------------------------------------------------- one screen (the audit's F6)
def output_screens(panel: ToolPanel) -> float:
    pane = panel.results
    body = pane.scroll_area.widget()
    assert body is not None
    return body.height() / pane.scroll_area.viewport().height()


def test_six_question_report_fits_one_screen(
    window: MainWindow, qtbot: QtBot, example_marks_max: Path
) -> None:
    """5.2 screens before the redesign (docs/audits/2026-10-09.md §1)."""
    panel = marks_panel(window)
    analyse(panel, qtbot, example_marks_max)
    assert output_screens(panel) <= 1.0
    assert panel.results.scroll_area.verticalScrollBar().maximum() == 0


def test_twenty_question_report_stays_within_two_screens(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    rng = random.Random(87)
    qcols = [f"q{i}" for i in range(1, 21)]
    rows = [["MAX", *[6] * 20]] + [
        [str(n), *[rng.randint(0, 6) for _ in qcols]] for n in range(1, 31)
    ]
    src = tmp_path / "twenty.csv"
    src.write_text(
        "# FAKE DATA\n" + "\n".join(",".join(map(str, r)) for r in [["row", *qcols], *rows])
    )
    assert read_table(src).shape == (31, 21)
    panel = marks_panel(window)
    analyse(panel, qtbot, src)
    assert panel.results.tables["questions"][0].rowCount() == 20
    assert output_screens(panel) <= 2.0


def test_stat_tiles_round_trip_through_a_table() -> None:
    from staffroom.core.panel import Stat, stat_table, stats_from_table

    stats = [Stat("Mean", "75%", "29.9 / 40"), Stat("Reteach first", "q6", action=True)]
    table = stat_table(stats)
    assert isinstance(table, Table) and stats_from_table(table) == stats
