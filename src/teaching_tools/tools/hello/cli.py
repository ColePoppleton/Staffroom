"""``tt hello ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from teaching_tools.core.config import load_config
from teaching_tools.core.csvio import read_table
from teaching_tools.core.paths import default_output_dir
from teaching_tools.core.plugin import RunContext, ToolError
from teaching_tools.tools.hello.logic import Options

SourceArg = Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="CSV or XLSX")]


def register(app: typer.Typer) -> None:
    @app.command()
    def run(
        source: SourceArg,
        out: Annotated[Path | None, typer.Option("--out", "-o", help="Output folder")] = None,
        lowercase: Annotated[bool, typer.Option(help="Keep the case of the names")] = False,
    ) -> None:
        """Add an Initials column to SOURCE and write <name>_with_initials.<ext>."""
        from teaching_tools.tools.hello import plugin

        config = load_config()
        ctx = RunContext(
            config=config,
            output_dir=out or default_output_dir(source, config.general.output_dir),
            progress=lambda _f, msg: typer.secho(msg, dim=True, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        options = Options(uppercase=not lowercase)
        try:
            result = plugin.run({"source": source, "options": options}, ctx)
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        typer.echo(result.summary)

    @app.command()
    def preview(source: SourceArg, rows: int = 10) -> None:
        """Print the first ROWS rows of SOURCE."""
        table = read_table(source)
        typer.echo(" | ".join(table.columns))
        for row in table.rows[:rows]:
            typer.echo(" | ".join("" if c is None else str(c) for c in row))
