"""``staff hello ...`` commands. Thin: parse arguments, call the plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from staffroom.core.config import load_config
from staffroom.core.csvio import read_table
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.hello.logic import Options
from staffroom.tools.hello.panel import output_folder

SourceArg = Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="CSV or XLSX")]


def register(app: typer.Typer) -> None:
    @app.command()
    def run(
        source: SourceArg,
        out: Annotated[Path | None, typer.Option("--out", "-o", help="Output folder")] = None,
        prefix: Annotated[str, typer.Option(help="Question column prefix")] = "q",
    ) -> None:
        """Summarise SOURCE per question (answered, mean, highest) into the output folder.

        Nothing per script is saved; --out picks a different folder for this run only.

        Example: staff hello run examples/marks_10x.csv
        """
        from staffroom.tools.hello import plugin

        config = load_config()
        config.read_only = True  # --out is for this run only; never saved to Settings
        if out is not None:
            config.general.output_dir = str(out)
        ctx = RunContext(
            config=config,
            output_dir=output_folder({}, config),
            progress=lambda _f, msg: typer.secho(msg, dim=True, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        try:
            result = plugin.run({"source": source, "options": Options(prefix=prefix)}, ctx)
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        typer.echo(result.summary)

    @app.command()
    def preview(source: SourceArg, rows: int = 10) -> None:
        """Print the first ROWS rows of SOURCE on screen; nothing is saved.

        Example: staff hello preview examples/marks_10x.csv --rows 5
        """
        table = read_table(source)
        if table.dropped_columns:
            typer.secho("dropped identifier columns: " + ", ".join(table.dropped_columns), err=True)
        typer.echo(" | ".join(table.columns))
        for row in table.rows[:rows]:
            typer.echo(" | ".join("" if c is None else str(c) for c in row))
