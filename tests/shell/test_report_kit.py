"""The report pieces added for marks (#87) are kit pieces: any tool can use
them from ``core.panel``. A stand-in tool uses each one outside marks, in the
default tabs layout, and the spec rejects the shapes the widgets cannot draw."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.panel import (
    BarChart,
    BarColumn,
    Choice,
    Column,
    EditableTable,
    FilePicker,
    LogArea,
    OptionsForm,
    PanelSpec,
    ResultsTable,
    Stat,
    StatTiles,
    TablePreview,
    stat_table,
)
from staffroom.core.plugin import Inputs, RunContext, RunResult
from staffroom.core.table import Table
from staffroom.shell.tool_panel import ToolPanel


@dataclass
class Opts:
    level: int = field(default=1, metadata={"label": "Level"})
    hidden: str = "kept"


class Survey:
    """Not marks: a quiz-results summary with the same report pieces."""

    name = "survey_standin"
    description = "Stand-in using the report kit"
    version = "0.0.0"

    def register_cli(self, app: Any) -> None:
        pass

    def panel_spec(self) -> PanelSpec:
        return PanelSpec(
            title="Survey",
            inputs=(
                FilePicker(key="data", label="Results", chip=True, required=False),
                TablePreview(key="rows", source="data", compact=True),
                Choice(key="mode", label="Count", choices=(("all", "All"), ("first", "First"))),
                OptionsForm(key="options", schema=Opts, fields=("level",)),
            ),
            outputs=(
                StatTiles(key="tiles"),
                BarChart(key="answers", label="Answers", category="Answer", value="Votes"),
                ResultsTable(
                    key="items",
                    label="Items",
                    bars=(BarColumn("Score", 10),),
                    tag_column="Flag",
                    hidden_columns=("Why",),
                ),
                LogArea(),
            ),
        )

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        assert inputs["options"] == Opts(level=1, hidden="kept")
        return RunResult(
            tables={
                "tiles": stat_table([Stat("Answers", "12"), Stat("Mode", inputs["mode"])]),
                "answers": Table(["Answer", "Votes"], [["A", 5], ["B", 7]]),
                "items": Table(
                    ["Item", "Score", "Flag", "Why"],
                    [["i1", 2.5, "check", "low"], ["i2", 9.0, "", ""]],
                ),
            },
            summary="done",
        )


@pytest.fixture
def panel(qtbot: QtBot) -> ToolPanel:
    widget = ToolPanel(Survey(), load_config())  # type: ignore[arg-type]
    qtbot.addWidget(widget)
    widget.resize(1000, 700)
    widget.show()
    return widget


def test_kit_pieces_render_outside_marks(panel: ToolPanel, qtbot: QtBot, tmp_path: Path) -> None:
    pane = panel.results
    assert pane.tabs is not None  # tabs layout: chart and table are tabs
    assert pane.top_keys == ["tiles"] and pane.main_keys == ["answers", "items"]
    assert not pane.sections["tiles"].isVisible()  # tiles show once filled
    panel.choices["mode"].set_value("first")
    assert "rows" not in panel.previews and "rows" in panel.summaries
    src = tmp_path / "r.csv"
    src.write_text("# FAKE DATA\nAnswer,Votes\nA,5\n")
    panel.set_input_path("data", src)
    assert [n.text for n in panel.summaries["rows"].notes()] == ["1 rows × 2 columns"]
    with qtbot.waitSignal(panel.run_finished, timeout=10000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.run_bar.status.text()
    QApplication.processEvents()
    assert pane.tiles["tiles"].values() == {"Answers": "12", "Mode": "first"}
    assert pane.sections["tiles"].isVisible()
    chart = pane.charts["answers"]
    assert [(b.category, b.value) for b in chart.canvas.bars] == [("A", 5.0), ("B", 7.0)]
    assert pane.corner_buttons["answers"] is chart.toggle  # the switch sits in the tab corner
    model, view, _caption = pane.tables["items"]
    assert model.tag(0) == "check" and model.tag(1) == ""
    assert view.isColumnHidden(2) and view.isColumnHidden(3)
    assert model.index(0, 0).data(3) == "Why: low"  # ToolTipRole
    pane.clear()
    assert not pane.sections["tiles"].isVisible() and chart.canvas.bars == []


def test_spec_rejects_what_the_widgets_cannot_draw() -> None:
    with pytest.raises(ValueError, match="two columns"):
        PanelSpec(
            title="x",
            inputs=(EditableTable(key="g", label="g", columns=(Column("a"),), compact=True),),
        )
    with pytest.raises(ValueError, match="not in its schema"):
        PanelSpec(title="x", inputs=(OptionsForm(key="o", schema=Opts, fields=("nope",)),))
    with pytest.raises(ValueError, match="must come after its FilePicker"):
        PanelSpec(
            title="x",
            inputs=(
                TablePreview(key="p", source="f", compact=True),
                FilePicker(key="f", label="f"),
            ),
        )
    with pytest.raises(ValueError, match="include its default"):
        Choice(key="c", label="c", choices=(("a", "A"),), default="b")
    with pytest.raises(ValueError, match="duplicate"):
        PanelSpec(
            title="x",
            inputs=(
                Choice(key="unit", label="u", choices=(("a", "A"),)),
                EditableTable(
                    key="g",
                    label="g",
                    columns=(Column("a"), Column("b", "float")),
                    compact=True,
                    choice=Choice(key="unit", label="u", choices=(("a", "A"),)),
                ),
            ),
        )
