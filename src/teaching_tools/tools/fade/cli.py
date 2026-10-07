"""``tt fade ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from teaching_tools.core.config import load_config
from teaching_tools.core.paths import default_output_dir
from teaching_tools.core.plugin import RunContext, ToolError
from teaching_tools.tools.fade.logic import Options


def register(app: typer.Typer) -> None:
    @app.command()
    def make(
        source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="A .py file")],
        steps: Annotated[int, typer.Option("--steps", "-k", help="How many versions")] = 4,
        order: Annotated[
            str, typer.Option("--order", help="bottom_up, top_down or ranges")
        ] = "bottom_up",
        ranges: Annotated[
            str, typer.Option("--ranges", help="e.g. 3-5,8 with --order ranges")
        ] = "",
        blank_headers: Annotated[
            bool, typer.Option("--blank-headers", help="Allow def/if/for/while to fade")
        ] = False,
        fmt: Annotated[str, typer.Option("--format", "-f", help="both, docx or pdf")] = "both",
        out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
        preview: Annotated[
            bool, typer.Option("--preview/--no-preview", help="Print the sheet and key")
        ] = True,
    ) -> None:
        """Write K progressively faded versions of SOURCE plus the solution as key."""
        from teaching_tools.tools.fade import plugin

        if order not in ("bottom_up", "top_down", "ranges"):
            typer.secho("--order must be bottom_up, top_down or ranges", fg="red", err=True)
            raise typer.Exit(1)
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
        options = Options(
            steps=steps,
            order=order,  # type: ignore[arg-type]
            ranges=ranges,
            keep_headers=not blank_headers,
            formats=fmt,  # type: ignore[arg-type]
        )
        try:
            result = plugin.run({"source": source, "options": options}, ctx)
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        if preview:
            typer.echo(result.texts["preview"])
        typer.echo(result.summary)
