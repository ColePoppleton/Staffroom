"""``staff worksheet ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from staffroom.core import spec
from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.worksheet.lessons import (
    LEGACY,
    UNITS,
    off_board_reason,
    resolve,
)
from staffroom.tools.worksheet.logic import LAW_FAMILIES, Options


def register(app: typer.Typer) -> None:
    @app.command()
    def make(
        unit: Annotated[
            str | None,
            typer.Argument(help="The unit, e.g. binary (see  staff worksheet lessons)"),
        ] = None,
        lesson: Annotated[
            str | None,
            typer.Option(
                "--lesson",
                "-l",
                help="A lesson of the unit, e.g. denary-to-binary; left out, the unit's Review",
            ),
        ] = None,
        topic: Annotated[
            str | None,
            typer.Option(
                "--topic", "-t", help="An old topic name (binary, shifts, …): its Review sheet"
            ),
        ] = None,
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
            str | None,
            typer.Option("--board", help=f"{spec.board_choices()}; defaults to the config setting"),
        ] = None,
        fmt: Annotated[str, typer.Option("--format", "-f", help="both, docx or pdf")] = "both",
        out: Annotated[Path | None, typer.Option("--out", "-o", help="Output folder")] = None,
        preview: Annotated[
            bool, typer.Option("--preview/--no-preview", help="Print the sheet and key")
        ] = True,
    ) -> None:
        """Make a lesson sheet, with an answer key.

        Example: staff worksheet make binary --lesson denary-to-binary --count 10

        A unit with no --lesson makes its Review sheet, the mixed sheet the tool
        made before lessons; so does an old --topic name, with the same seeds.
        """
        from staffroom.tools.worksheet import plugin

        if unit is not None and topic is not None:
            typer.secho("Give a unit or --topic, not both.", fg="red", err=True)
            raise typer.Exit(1)
        try:
            chosen = resolve(unit or topic or "binary", lesson)
        except ValueError as exc:
            typer.secho(f"{exc}; see  staff worksheet lessons", fg="red", err=True)
            raise typer.Exit(1) from None
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
            if board.lower() not in spec.BOARDS:
                typer.secho(f"--board {spec.board_choices('|', '|')}", fg="red", err=True)
                raise typer.Exit(1)
            config.general.board = board.lower()  # this run only; the config file is not saved
        ctx = RunContext(
            config=config,
            output_dir=out or config.output_dir_for(None, "worksheet"),
            progress=lambda _f, msg: typer.secho(msg, dim=True, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        options = Options(
            count=count,
            seed=seed,
            difficulty=difficulty,  # type: ignore[arg-type]
            formats=fmt,  # type: ignore[arg-type]
        )
        inputs = {"lesson": chosen.key, "options": options, "level": level, "laws": laws}
        try:
            result = plugin.run(inputs, ctx)
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        if preview:
            typer.echo(result.texts["preview"])
        typer.echo(result.summary)

    def list_lessons(unit: str | None) -> None:
        board = load_config().general.board
        short = spec.SHORT_NAMES
        name = short.get(board, board.upper())
        for u in UNITS:
            if unit is not None and unit not in (u.slug, u.title):
                continue
            typer.echo(f"{u.slug}  ({u.title})")
            for les in u.lessons:
                if les.review:
                    where = f"old topic {les.legacy}"
                elif board in les.spec:
                    where = f"{name} {les.spec[board]}"
                else:
                    where = off_board_reason(les, board, short).lower()
                typer.echo(f"  {les.slug:<22} {les.title:<30} {where}")

    @app.command()
    def lessons(
        unit: Annotated[str | None, typer.Argument(help="Only this unit")] = None,
    ) -> None:
        """List the units and their lessons, with your board's spec point.

        Example: staff worksheet lessons binary
        """
        list_lessons(unit)

    @app.command()
    def topics() -> None:
        """List the units and lessons (the old name for  staff worksheet lessons).

        Example: staff worksheet topics
        """
        list_lessons(None)
        typer.echo("\nOld topic names still work with --topic: " + ", ".join(LEGACY))
