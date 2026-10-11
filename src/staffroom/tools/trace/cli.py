"""``staff trace ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.trace.logic import Options, stdin_option_step


def register(app: typer.Typer) -> None:
    @app.command()
    def make(
        source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="A .py file")],
        stdin: Annotated[str, typer.Option("--stdin", help="Inputs, use \\n between lines")] = "",
        steps: Annotated[int, typer.Option("--steps", help="Max steps")] = 60,
        variables: Annotated[str, typer.Option("--vars", help="Comma-separated columns")] = "",
        top_level_only: Annotated[
            bool,
            typer.Option(
                "--top-level-only",
                help="The Year 9 preset: leave out function scopes and their locals",
            ),
        ] = False,
        fmt: Annotated[str, typer.Option("--format", "-f", help="both, docx or pdf")] = "both",
        out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
        preview: Annotated[
            bool, typer.Option("--preview/--no-preview", help="Print the sheet and key")
        ] = True,
    ) -> None:
        """Trace SOURCE in the sandbox and write blank + completed trace tables.

        Example: staff trace make examples/year9.py --vars total,count,score
        """
        from staffroom.tools.trace import MissingInputError, plugin

        config = load_config()
        ctx = RunContext(
            config=config,
            output_dir=out or config.output_dir_for(source, "trace"),
            progress=lambda _f, msg: typer.secho(msg, dim=True, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        options = Options(
            max_steps=steps,
            top_level_only=top_level_only,
            variables=variables,
            formats=fmt,  # type: ignore[arg-type]
        )
        try:
            result = plugin.run(
                {"source": source, "stdin": stdin.replace("\\n", "\n"), "options": options}, ctx
            )
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            if isinstance(exc, MissingInputError):
                typer.secho(stdin_option_step(exc.needed), err=True)
            raise typer.Exit(1) from None
        if preview:
            typer.echo(result.texts["preview"])
        typer.echo(result.summary)
