"""Marks: raw marks → grades, distribution, question analysis. Class-level only."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from staffroom.core.csvio import read_table, write_table
from staffroom.core.panel import PanelSpec
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.core.table import Table
from staffroom.tools.marks import logic, presets
from staffroom.tools.marks.chart import distribution_chart
from staffroom.tools.marks.panel import panel_spec


class MarksPlugin:
    name = "marks"
    description = "Raw marks → grades, distribution chart, facility and discrimination."
    version = "0.1.0"

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.marks.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        source: Path | None = inputs.get("marks")
        if source is None:
            raise ToolError("Choose a marks file first.")
        options: logic.Options = inputs.get("options", logic.Options())
        boundaries: Table = inputs.get(
            "boundaries", presets.preset_table(presets.BUILTIN_PRESETS[presets.DEFAULT_PRESET])
        )

        ctx.progress(0.1, f"Reading {source.name}")
        table = read_table(source)
        if table.dropped_columns:
            ctx.log("Dropped identifier column(s), never used: " + ", ".join(table.dropped_columns))
        ctx.progress(0.4, "Analysing")
        try:
            analysis = logic.analyse(table, boundaries, options)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        for warning in analysis.warnings:
            ctx.log("Warning: " + warning)
        ctx.log(
            f"{len(analysis.grades)} scripts, paper total {analysis.total_max:g} "
            f"({', '.join(f'{q}={m:g}' for q, m in analysis.max_marks.items())})"
        )

        ctx.progress(0.7, "Drawing chart")
        out = ctx.output_dir
        stem = source.stem
        chart = distribution_chart(
            analysis.distribution, out / f"{stem}_distribution.png", ctx.config.general.theme
        )
        # Aggregates only. The per-script table is never written.
        dist_csv = write_table(
            _marked(analysis.distribution, table), out / f"{stem}_distribution.csv"
        )
        q_csv = write_table(_marked(analysis.questions, table), out / f"{stem}_questions.csv")
        ctx.progress(1.0, "Done")
        return RunResult(
            tables={
                "distribution": analysis.distribution,
                "questions": analysis.questions,
                "worst": analysis.worst,
                "grades": analysis.grades,
            },
            images={"chart": chart},
            files=[dist_csv, q_csv, chart],
            summary=f"{len(analysis.grades)} scripts graded; aggregates saved to {out}",
        )

    def act(self, name: str, row: Mapping[str, Any], ctx: RunContext) -> RunResult:
        if name == "save_preset":
            preset_name = str(row.get("name", "")).strip()
            table = row.get("table")
            if not preset_name or not isinstance(table, Table):
                raise ToolError("A preset needs a name and a boundaries table.")
            presets.save_preset(ctx.config, preset_name, table)
            return RunResult(summary=f"Saved preset {preset_name!r} to {ctx.config.path}")
        raise ToolError(f"Unknown action {name!r}")


def _marked(table: Table, source: Table) -> Table:
    table.fake_data = source.fake_data
    return table


plugin = MarksPlugin()
