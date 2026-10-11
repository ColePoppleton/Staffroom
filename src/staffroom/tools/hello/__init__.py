"""Hello: the reference tool, and what ``staff new`` generates (#18).

It reads a marks file (one row per script, q1..qn, no identifiers) and saves
one row per question: how many scripts have a mark, the mean and the highest.
It exists to prove the plugin contract end to end and to show the two rules
every tool keeps (docs/adding-a-tool.md):

* Nothing per row is saved. A run writes an aggregate, a sheet, a key or a
  chart; never the input's rows with a column added.
* Files go to the output folder (``panel.output_folder``), never next to the
  input, which may sit in a shared or tracked folder such as ``examples/``.

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
from staffroom.tools.hello.panel import output_folder, panel_spec


class HelloPlugin:
    name = "hello"
    description = "Summarise a marks file per question (reference tool)."
    version = "0.3.0"
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
        options: logic.Options = inputs.get("options") or logic.Options()

        ctx.progress(0.1, f"Reading {source.name}")
        table = read_table(source)  # identifier columns are already gone
        if table.dropped_columns:
            ctx.log("Dropped identifier column(s): " + ", ".join(table.dropped_columns))

        ctx.progress(0.5, "Summarising")
        try:
            summary = logic.summarise(table, options)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

        # Not ctx.output_dir: with nothing set in Settings that is the input's
        # own folder. A summary of a file goes to the output folder instead.
        folder = output_folder(inputs, ctx.config)
        out = write_table(summary, folder / f"{source.stem}_summary.csv")
        ctx.progress(1.0, "Done")
        return RunResult(
            tables={"questions": summary},
            files=[out],
            summary=f"Summarised {len(summary)} questions from {len(table)} scripts into {out}",
            outcome=f"{len(summary)} questions · {len(table)} scripts",
        )


plugin = HelloPlugin()
