"""``staff worksheet ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.worksheet.logic import GENERATORS, LAW_FAMILIES, TOPIC_TITLES, Options


def register(app: typer.Typer) -> None:
    @app.command()
    def make(
        topic: Annotated[
            str, typer.Option("--topic", "-t", help="See  staff worksheet topics")
        ] = "binary",
        count: Annotated[int, typer.Option("--count", "-n")] = 10,
        seed: Annotated[int, typer.Option("--seed", "-s")] = 42,
        difficulty: Annotated[
            str, typer.Option("--difficulty", help="easy, medium, hard")
        ] = "medium",
        level: Annotated[
            str,
            typer.Option(
                "--level",
                help="gcse or a_level (A-level truth tables add XOR, and NAND/NOR at hard)",
            ),
        ] = "gcse",
        laws: Annotated[
            str,
            typer.Option(
                "--laws", help="Simplification laws: absorption, de_morgan, identities, all"
            ),
        ] = "absorption",
        board: Annotated[
            str | None, typer.Option("--board", help="ocr or aqa; defaults to the config setting")
        ] = None,
        fmt: Annotated[str, typer.Option("--format", "-f", help="both, docx or pdf")] = "both",
        out: Annotated[Path | None, typer.Option("--out", "-o", help="Output folder")] = None,
        preview: Annotated[
            bool, typer.Option("--preview/--no-preview", help="Print the sheet and key")
        ] = True,
    ) -> None:
        """Make a worksheet on one topic, with an answer key.

        Example: staff worksheet make --topic binary --count 10
        """
        from staffroom.tools.worksheet import plugin

        if topic not in GENERATORS:
            typer.secho(f"unknown topic {topic!r}; see  staff worksheet topics", fg="red", err=True)
            raise typer.Exit(1)
        if difficulty not in ("easy", "medium", "hard") or fmt not in ("both", "docx", "pdf"):
            typer.secho("--difficulty easy|medium|hard, --format both|docx|pdf", fg="red", err=True)
            raise typer.Exit(1)
        if level not in ("gcse", "a_level") or laws not in LAW_FAMILIES:
            typer.secho(
                f"--level gcse|a_level, --laws {'|'.join(LAW_FAMILIES)}", fg="red", err=True
            )
            raise typer.Exit(1)
        config = load_config()
        if board is not None:
            if board.lower() not in ("ocr", "aqa"):
                typer.secho("--board ocr|aqa", fg="red", err=True)
                raise typer.Exit(1)
            config.general.board = board.lower()  # this run only; the config file is not saved
        ctx = RunContext(
            config=config,
            output_dir=out or config.output_dir_for(None, "worksheet"),
            progress=lambda _f, msg: typer.secho(msg, dim=True, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        options = Options(
            topic=topic,  # type: ignore[arg-type]
            count=count,
            seed=seed,
            difficulty=difficulty,  # type: ignore[arg-type]
            level=level,  # type: ignore[arg-type]
            laws=laws,  # type: ignore[arg-type]
            formats=fmt,  # type: ignore[arg-type]
        )
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
        """List the topics a worksheet can be made on.

        Example: staff worksheet topics
        """
        for name, title in TOPIC_TITLES.items():
            typer.echo(f"{name:<24} {title}")
