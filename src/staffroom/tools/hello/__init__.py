"""Hello: the reference tool. Reads a marks file (one row per script, q1..qn,
no identifiers), previews it, writes it back with a Total column. Exists to
prove the plugin contract end to end and as the model for ``staff new``.

It is ``hidden``: not a teaching tool, so it stays out of the launcher
sidebar and the number shortcuts. ``staff hello run`` and
``staffroom --tool hello`` still work, and ``staff list`` shows it marked."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from staffroom.core.csvio import read_table, write_table
from staffroom.core.panel import PanelSpec
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.tools.hello import logic
from staffroom.tools.hello.panel import panel_spec


class HelloPlugin:
    name = "hello"
    description = "Add a Total column to a marks file (reference tool)."
    version = "0.2.0"
    hidden = True  # the reference for developers, not a tool for teachers

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.hello.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        source: Path | None = inputs.get("source")
        if source is None:
            raise ToolError("Choose a marks file first.")
        options: logic.Options = inputs.get("options", logic.Options())

        ctx.progress(0.1, f"Reading {source.name}")
        table = read_table(source)
        if table.dropped_columns:
            ctx.log("Dropped identifier column(s): " + ", ".join(table.dropped_columns))
        ctx.log(f"Read {len(table)} rows, columns: {', '.join(table.columns)}")

        ctx.progress(0.5, "Totalling")
        try:
            result = logic.add_total(table, options)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

        out = ctx.output_dir / f"{source.stem}_totals{source.suffix}"
        write_table(result, out)
        ctx.progress(1.0, "Done")
        return RunResult(
            tables={"result": result},
            files=[out],
            summary=f"Wrote {len(result)} rows to {out}",
            outcome=f"{len(result)} rows totalled",
        )


plugin = HelloPlugin()
