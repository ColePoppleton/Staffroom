"""``staff hello ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from staffroom.core.config import load_config
from staffroom.core.csvio import read_table
from staffroom.core.paths import default_output_dir
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.hello.logic import Options

SourceArg = Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="CSV or XLSX")]


def register(app: typer.Typer) -> None:
    @app.command()
    def run(
        source: SourceArg,
        out: Annotated[Path | None, typer.Option("--out", "-o", help="Output folder")] = None,
        prefix: Annotated[str, typer.Option(help="Question column prefix")] = "q",
        max_marks: Annotated[int, typer.Option(help="Paper total; adds a Percent column")] = 0,
    ) -> None:
        """Add a Total column to SOURCE and write <name>_totals.<ext>."""
        from staffroom.tools.hello import plugin

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
        options = Options(prefix=prefix, max_marks=max_marks)
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
        if table.dropped_columns:
            typer.secho("dropped identifier columns: " + ", ".join(table.dropped_columns), err=True)
        typer.echo(" | ".join(table.columns))
        for row in table.rows[:rows]:
            typer.echo(" | ".join("" if c is None else str(c) for c in row))
