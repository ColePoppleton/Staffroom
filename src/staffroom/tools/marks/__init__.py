"""Marks: raw marks → grades, distribution, question analysis. Class-level only."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from staffroom.core.csvio import read_table, write_table
from staffroom.core.panel import PanelSpec, Stat, stat_table
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.core.table import Table
from staffroom.tools.marks import logic, presets
from staffroom.tools.marks.chart import distribution_chart
from staffroom.tools.marks.panel import panel_spec


class MarksPlugin:
    name = "marks"
    description = "Raw marks → grades, distribution chart, facility and discrimination."
    version = "0.1.0"
    group, glyph = "After a test", "chart"  # sidebar group and glyph (#89)

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
        unit = inputs.get("unit")
        if unit in ("percent", "raw"):  # the panel's switch beside the boundaries
            options = dataclasses.replace(options, unit=unit)
        boundaries: Table = inputs.get(
            "boundaries", presets.preset_table(presets.BUILTIN_PRESETS[presets.DEFAULT_PRESET])
        )

        ctx.progress(0.1, f"Reading {source.name}")
        # The MAX row is found on the raw file, before identifier columns go:
        # a markbook export keeps the flag in the name column.
        table = read_table(source, flag=logic.MAX_FLAG)
        if table.dropped_columns:
            ctx.log("Dropped identifier column(s), never used: " + ", ".join(table.dropped_columns))
        ctx.progress(0.4, "Analysing")
        try:
            analysis = logic.analyse(table, boundaries, options)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        for warning in analysis.warnings:
            ctx.warn(warning)
        ctx.log(
            f"{len(analysis.grades)} scripts, paper total {analysis.total_max:g} "
            f"({', '.join(f'{q}={m:g}' for q, m in analysis.max_marks.items())})"
        )

        ctx.progress(0.7, "Drawing chart")
        out = ctx.output_dir
        stem = source.stem
        # Always light: the PNG is for reports and slides, not the screen (#13).
        chart = distribution_chart(
            logic.without_incomplete_row(analysis.distribution), out / f"{stem}_distribution.png"
        )
        # Aggregates only. The per-script table is never written.
        dist_csv = write_table(
            _marked(analysis.distribution, table), out / f"{stem}_distribution.csv"
        )
        q_csv = write_table(_marked(analysis.questions, table), out / f"{stem}_questions.csv")
        ctx.progress(1.0, "Done")
        n_warn = len(analysis.warnings)
        caveat = "" if not n_warn else f"{n_warn} warning{'s' if n_warn > 1 else ''} in the log; "
        return RunResult(
            # On screen only: none of these is written except as the two CSVs above.
            tables={
                "headline": stat_table(headline_stats(analysis)),
                "distribution": analysis.distribution,
                "questions": analysis.report_questions,
                "grades": analysis.grades,
            },
            images={"chart": chart},
            texts={"distribution": boundary_caption(boundaries, options, ctx)},
            files=[dist_csv, q_csv, chart],
            summary=f"{len(analysis.grades)} scripts graded; {caveat}aggregates saved to {out}",
            outcome=f"{len(analysis.grades)} scripts graded · out of {analysis.total_max:g}",
            labels={chart: "Chart"},
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


def headline_stats(analysis: logic.Analysis) -> list[Stat]:
    """The four tiles: scripts, mean, median grade, what to reteach first."""
    h = analysis.headline
    incomplete = analysis.incomplete_scripts
    passing = f"{h.at_or_above_pass} of {h.scripts} at {h.pass_grade}+" if h.pass_grade else ""
    overall = f"{h.mean_percent:.0f}%"
    reteach = ", ".join(h.reteach)
    return [
        Stat("Scripts", str(h.scripts), f"{incomplete} incomplete" if incomplete else ""),
        Stat("Mean", overall, f"{h.mean_total:.1f} / {h.total_max:g}"),
        Stat("Median grade", h.median_grade, passing),
        Stat(
            "Reteach first",
            reteach or "None",
            f"facility under {h.reteach_below:.2f}"
            if reteach
            else f"no facility under {h.reteach_below:.2f}",
            action=bool(reteach),
        ),
    ]


def boundary_caption(boundaries: Table, options: logic.Options, ctx: RunContext) -> str:
    """Which boundaries graded the chart: the preset's name when they match one."""
    rows = tuple(tuple(r[:2]) for r in boundaries.rows if r and r[0] is not None)
    name = next(
        (n for n, p in presets.all_presets(ctx.config).items() if _same_rows(p, rows)),
        "Custom boundaries",
    )
    return f"{name.split(' (')[0]} · {'%' if options.unit == 'percent' else 'raw'}"


def _same_rows(a: tuple[tuple[object, ...], ...], b: tuple[tuple[object, ...], ...]) -> bool:
    if len(a) != len(b):
        return False
    for (g1, m1), (g2, m2) in zip((r[:2] for r in a), (r[:2] for r in b), strict=True):
        if str(g1) != str(g2) or logic.as_mark(m1) != logic.as_mark(m2):  # type: ignore[arg-type]
            return False
    return True


def _marked(table: Table, source: Table) -> Table:
    table.fake_data = source.fake_data
    return table


plugin = MarksPlugin()
