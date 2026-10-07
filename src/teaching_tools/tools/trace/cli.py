"""``tt trace ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from teaching_tools.core.config import load_config
from teaching_tools.core.paths import default_output_dir
from teaching_tools.core.plugin import RunContext, ToolError
from teaching_tools.tools.trace.logic import Options


def register(app: typer.Typer) -> None:
    @app.command()
    def make(
        source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="A .py file")],
        stdin: Annotated[str, typer.Option("--stdin", help="Inputs, use \\n between lines")] = "",
        steps: Annotated[int, typer.Option("--steps", help="Max steps")] = 60,
        variables: Annotated[str, typer.Option("--vars", help="Comma-separated columns")] = "",
        fmt: Annotated[str, typer.Option("--format", "-f", help="both, docx or pdf")] = "both",
        out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
        preview: Annotated[
            bool, typer.Option("--preview/--no-preview", help="Print the sheet and key")
        ] = True,
    ) -> None:
        """Trace SOURCE in the sandbox and write blank + completed trace tables."""
        from teaching_tools.tools.trace import plugin

        config = load_config()
        ctx = RunContext(
            config=config,
            output_dir=out
            or default_output_dir(
                source, config.general.output_dir, resources_root=config.general.resources_root
            ),
            progress=lambda _f, msg: typer.secho(msg, dim=True, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        options = Options(max_steps=steps, variables=variables, formats=fmt)  # type: ignore[arg-type]
        try:
            result = plugin.run(
                {"source": source, "stdin": stdin.replace("\\n", "\n"), "options": options}, ctx
            )
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        if preview:
            typer.echo(result.texts["preview"])
        typer.echo(result.summary)
