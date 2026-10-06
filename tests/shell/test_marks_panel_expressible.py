"""The forthcoming ``marks`` tool needs: a file picker, an editable boundaries
table, a run button, a results table and a chart image. This proves the panel
vocabulary and the widget kit can express and render exactly that, using a
stand-in plugin that draws a PNG without any plotting library."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any

from pytestqt.qtbot import QtBot

from teaching_tools.core.config import load_config
from teaching_tools.core.panel import (
    Column,
    EditableTable,
    FilePicker,
    ImageView,
    LogArea,
    PanelSpec,
    ResultsTable,
    TablePreview,
)
from teaching_tools.core.plugin import Inputs, RunContext, RunResult
from teaching_tools.core.table import Table
from teaching_tools.shell.tool_panel import ToolPanel

BOUNDARIES = EditableTable(
    key="boundaries",
    label="Grade boundaries",
    columns=(Column("Grade", "text", 80), Column("Min mark", "int", 90)),
    rows=(("9", 36), ("7", 28), ("5", 20), ("4", 16), ("1", 0)),
    help="Lowest raw mark for each grade. Edit to try different boundaries.",
)


class MarksStandIn:
    name = "marks_standin"
    description = "Stand-in for the marks tool"
    version = "0.0.0"

    def register_cli(self, app: Any) -> None:
        pass

    def panel_spec(self) -> PanelSpec:
        return PanelSpec(
            title="Marks",
            description="Raw marks to grades, per-question analysis and cohort distribution.",
            inputs=(
                FilePicker(key="marks", label="Marks file"),
                TablePreview(key="preview", source="marks"),
                BOUNDARIES,
            ),
            outputs=(
                ResultsTable(key="grades", label="Grades"),
                ResultsTable(key="questions", label="Per-question analysis"),
                ImageView(key="distribution", label="Cohort distribution"),
                LogArea(),
            ),
            run_label="Analyse",
        )

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        boundaries: Table = inputs["boundaries"]
        assert boundaries.columns == ["Grade", "Min mark"]
        png = ctx.output_dir / "distribution.png"
        png.write_bytes(_tiny_png())
        return RunResult(
            tables={
                "grades": Table(["Name", "Total", "Grade"], [["Ada", 37, "9"]]),
                "questions": Table(["Q", "Mean %"], [["Q1", 80.0]]),
            },
            images={"distribution": png},
            files=[png],
            summary=f"{len(boundaries)} boundaries applied",
        )


def _tiny_png() -> bytes:
    raw = b"".join(b"\x00" + b"\x6d\x8d\xff" * 4 for _ in range(4))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def test_marks_panel_renders_and_runs(qtbot: QtBot, tmp_path: Path, example_marks: Path) -> None:
    config = load_config()
    config.general.output_dir = str(tmp_path)
    panel = ToolPanel(MarksStandIn(), config)
    qtbot.addWidget(panel)
    panel.show()

    grid = panel.grids["boundaries"]
    assert grid.model.rowCount() == 5
    grid.add_row()
    assert grid.model.rowCount() == 6
    grid.remove_selected()  # nothing selected: no-op
    assert grid.value().columns == ["Grade", "Min mark"]

    panel.set_input_path("marks", example_marks)
    assert panel.previews["preview"].model.columnCount() == 8

    with qtbot.waitSignal(panel.run_finished, timeout=5000) as blocker:
        panel.start_run()
    assert blocker.args == [True]
    assert panel.results.tables["grades"][0].rowCount() == 1
    assert panel.results.tables["questions"][0].rowCount() == 1
    image = panel.results.images["distribution"]
    assert image.pixmap() is not None and not image.pixmap().isNull()
    assert "6 boundaries" in panel.run_bar.status.text()
