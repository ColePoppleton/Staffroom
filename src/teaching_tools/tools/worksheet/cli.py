"""``tt worksheet ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from teaching_tools.core.config import load_config
from teaching_tools.core.paths import default_output_dir
from teaching_tools.core.plugin import RunContext, ToolError
from teaching_tools.tools.worksheet.logic import GENERATORS, TOPIC_TITLES, Options


def register(app: typer.Typer) -> None:
    @app.command()
    def make(
        topic: Annotated[
            str, typer.Option("--topic", "-t", help="See  tt worksheet topics")
        ] = "binary",
        count: Annotated[int, typer.Option("--count", "-n")] = 10,
        seed: Annotated[int, typer.Option("--seed", "-s")] = 42,
        difficulty: Annotated[
            str, typer.Option("--difficulty", help="easy, medium, hard")
        ] = "medium",
        fmt: Annotated[str, typer.Option("--format", "-f", help="both, docx or pdf")] = "both",
        out: Annotated[Path | None, typer.Option("--out", "-o", help="Output folder")] = None,
        preview: Annotated[
            bool, typer.Option("--preview/--no-preview", help="Print the sheet and key")
        ] = True,
    ) -> None:
        """Make a worksheet and answer key."""
        from teaching_tools.tools.worksheet import plugin

        if topic not in GENERATORS:
            typer.secho(f"unknown topic {topic!r}; see  tt worksheet topics", fg="red", err=True)
            raise typer.Exit(1)
        if difficulty not in ("easy", "medium", "hard") or fmt not in ("both", "docx", "pdf"):
            typer.secho("--difficulty easy|medium|hard, --format both|docx|pdf", fg="red", err=True)
            raise typer.Exit(1)
        config = load_config()
        ctx = RunContext(
            config=config,
            output_dir=out or default_output_dir(None, config.general.output_dir),
            progress=lambda _f, msg: typer.secho(msg, dim=True, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        options = Options(topic=topic, count=count, seed=seed, difficulty=difficulty, formats=fmt)  # type: ignore[arg-type]
        try:
            result = plugin.run({"options": options}, ctx)
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        if preview:
            typer.echo(result.texts["preview"])
        typer.echo(result.summary)

    @app.command()
    def topics() -> None:
        """List the question generators."""
        for name, title in TOPIC_TITLES.items():
            typer.echo(f"{name:<24} {title}")
