"""Hello: the reference tool. Reads a class list, previews it, writes it back
with an ``Initials`` column. Exists to prove the plugin contract end to end."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from teaching_tools.core.csvio import read_table, write_table
from teaching_tools.core.panel import PanelSpec
from teaching_tools.core.plugin import Inputs, RunContext, RunResult, ToolError
from teaching_tools.tools.hello import logic
from teaching_tools.tools.hello.panel import panel_spec


class HelloPlugin:
    name = "hello"
    description = "Add an Initials column to a class list (reference tool)."
    version = "0.1.0"

    def register_cli(self, app: Any) -> None:
        from teaching_tools.tools.hello.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        source: Path | None = inputs.get("source")
        if source is None:
            raise ToolError("Choose a class list first.")
        options: logic.Options = inputs.get("options", logic.Options())

        ctx.progress(0.1, f"Reading {source.name}")
        table = read_table(source)
        ctx.log(f"Read {len(table)} rows, columns: {', '.join(table.columns)}")

        ctx.progress(0.5, "Computing initials")
        try:
            result = logic.add_initials(table, options)
        except KeyError as exc:
            raise ToolError(f"Missing column: {exc.args[0]}") from exc

        out = ctx.output_dir / f"{source.stem}_with_initials{source.suffix}"
        write_table(result, out)
        ctx.progress(1.0, "Done")
        return RunResult(
            tables={"result": result},
            files=[out],
            summary=f"Wrote {len(result)} rows to {out}",
        )


plugin = HelloPlugin()
