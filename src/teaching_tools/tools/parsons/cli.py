"""``tt parsons ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from teaching_tools.core.config import load_config
from teaching_tools.core.paths import default_output_dir
from teaching_tools.core.plugin import RunContext, ToolError
from teaching_tools.tools.parsons.logic import Options


def register(app: typer.Typer) -> None:
    @app.command()
    def make(
        source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="A .py file")],
        seed: Annotated[int, typer.Option("--seed", "-s")] = 1,
        distractors: Annotated[int, typer.Option("--distractors", "-d")] = 2,
        lines: Annotated[
            bool, typer.Option("--lines", help="Split per line, not per statement")
        ] = False,
        no_indent: Annotated[bool, typer.Option("--no-indent", help="Strip indentation")] = False,
        no_hint: Annotated[bool, typer.Option("--no-hint")] = False,
        fmt: Annotated[str, typer.Option("--format", "-f", help="both, docx or pdf")] = "both",
        out: Annotated[Path | None, typer.Option("--out", "-o", help="Output folder")] = None,
        preview: Annotated[
            bool, typer.Option("--preview/--no-preview", help="Print the sheet and key")
        ] = True,
    ) -> None:
        """Make a Parsons worksheet and answer key from SOURCE."""
        from teaching_tools.tools.parsons import plugin

        if fmt not in ("both", "docx", "pdf"):
            typer.secho("--format must be both, docx or pdf", fg="red", err=True)
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
            seed=seed,
            distractors=distractors,
            granularity="line" if lines else "statement",
            show_indentation=not no_indent,
            hint=not no_hint,
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
