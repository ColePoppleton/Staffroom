"""``staff quiz ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from staffroom.core import spec
from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.quiz.logic import Options

BANK_EXAMPLE = "examples/question_bank.md"

BankArg = Annotated[
    Path | None,
    typer.Argument(
        exists=True, dir_okay=False, show_default=False, help="The question bank (.md file)"
    ),
]
BankOpt = Annotated[
    Path | None,
    typer.Option(
        "--bank",
        "-b",
        exists=True,
        dir_okay=False,
        show_default=False,
        help="The question bank, if you prefer to name it with a flag",
    ),
]


def _bank(argument: Path | None, option: Path | None) -> Path:
    """The bank given as the argument or as ``--bank`` (the older spelling,
    kept so existing scripts still work). One is needed; two different ones
    are refused rather than one silently winning."""
    if argument is not None and option is not None and argument != option:
        raise typer.BadParameter(
            f"two different banks given ({argument} and {option}); give one",
            param_hint="BANK",
        )
    bank = argument or option
    if bank is None:
        raise typer.BadParameter(
            f"give the question bank file, e.g. {BANK_EXAMPLE}", param_hint="BANK"
        )
    return bank


def _ctx(bank: Path, out: Path | None) -> RunContext:
    config = load_config()
    return RunContext(
        config=config,
        output_dir=out or config.output_dir_for(bank, "quiz"),
        progress=lambda _f, msg: typer.secho(msg, dim=True, err=True),
        log=lambda msg: typer.echo(msg, err=True),
    )


def _run(inputs: dict[str, object], ctx: RunContext, preview: bool) -> None:
    from staffroom.tools.quiz import plugin

    try:
        result = plugin.run(inputs, ctx)
    except ToolError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    for row in result.tables["chosen"].rows:
        typer.echo(f"  {row[0]:>3}  {row[1]:<5} {row[2]}")
    if preview:
        typer.echo("\n" + result.texts["preview"])
    typer.echo(result.summary)


def register(app: typer.Typer) -> None:
    @app.command()
    def export(
        bank: BankArg = None,
        bank_flag: BankOpt = None,
        fmt: Annotated[
            str, typer.Option("--format", "-f", help="kahoot, forms or donow")
        ] = "kahoot",
        topics: Annotated[
            str, typer.Option("--topics", "-t", help="Comma-separated topic tags")
        ] = "",
        spec_: Annotated[str, typer.Option("--spec", help="Spec prefixes, e.g. ocr:1.2")] = "",
        n: Annotated[int, typer.Option("--n", "-n")] = 10,
        seed: Annotated[int, typer.Option("--seed", "-s")] = 1,
        title: Annotated[str, typer.Option("--title")] = "Do now",
        out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
        preview: Annotated[bool, typer.Option("--preview/--no-preview")] = False,
    ) -> None:
        """Pick N questions from a bank (by topic or spec point) and export them.

        Example: staff quiz export examples/question_bank.md --format donow --n 5
        """
        bank = _bank(bank, bank_flag)
        if fmt not in ("kahoot", "forms", "donow"):
            typer.secho("--format must be kahoot, forms or donow", fg="red", err=True)
            raise typer.Exit(1)
        options = Options(
            fmt=fmt,  # type: ignore[arg-type]
            count=n,
            seed=seed,
            topics=topics,
            spec=spec_,
            title=title,
        )
        _run({"source": bank, "options": options}, _ctx(bank, out), preview)

    @app.command()
    def retrieval(
        log: Annotated[
            Path, typer.Option("--log", "-l", exists=True, dir_okay=False, help="date,topic CSV")
        ],
        bank: BankArg = None,
        bank_flag: BankOpt = None,
        fmt: Annotated[str, typer.Option("--format", "-f")] = "donow",
        today: Annotated[str, typer.Option("--date", help="YYYY-MM-DD; default today")] = "",
        n: Annotated[int, typer.Option("--n", "-n")] = 10,
        seed: Annotated[int, typer.Option("--seed", "-s")] = 1,
        title: Annotated[str, typer.Option("--title")] = "Do now",
        out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
        preview: Annotated[bool, typer.Option("--preview/--no-preview")] = False,
    ) -> None:
        """Pick questions from the topics taught 1, 3 and 6 weeks before DATE.

        Example: staff quiz retrieval examples/question_bank.md --log examples/taught_log.csv
        """
        bank = _bank(bank, bank_flag)
        options = Options(
            fmt=fmt,  # type: ignore[arg-type]
            count=n,
            seed=seed,
            retrieval=True,
            today=today,
            title=title,
        )
        _run({"source": bank, "taught_log": log, "options": options}, _ctx(bank, out), preview)

    @app.command("list")
    def list_(bank: BankArg = None, bank_flag: BankOpt = None) -> None:
        """List the questions, topics and spec tags in a bank.

        Example: staff quiz list examples/question_bank.md
        """
        bank = _bank(bank, bank_flag)
        from staffroom.tools.quiz import load_bank

        try:
            loaded = load_bank(bank)
        except ToolError as exc:
            typer.secho(str(exc), fg="red", err=True)
            raise typer.Exit(1) from None
        for q in loaded.questions:
            typer.echo(f"{q.number:>3}  {q.qtype:<5} {q.text}  [{', '.join(q.tags)}]")
        typer.echo(f"{len(loaded.questions)} questions; topics: {', '.join(loaded.topics)}")

    @app.command()
    def check(bank: BankArg = None, bank_flag: BankOpt = None) -> None:
        """Check a bank and report every problem with its line number.

        Example: staff quiz check examples/question_bank.md
        """
        bank = _bank(bank, bank_flag)
        from staffroom.tools.quiz.logic import parse_bank

        loaded = parse_bank(bank.read_text(encoding="utf-8"))
        for err in loaded.errors:
            typer.echo(err)
        unknown = [t for q in loaded.questions for t in q.spec_tags if spec.find(t) is None]
        for t in sorted(set(unknown)):
            typer.echo(f"unknown spec tag: {t}")
        typer.echo(
            f"{len(loaded.questions)} questions, {len(loaded.errors)} problems, "
            f"{len(set(unknown))} unknown spec tags"
        )
        raise typer.Exit(1 if loaded.errors else 0)

    @app.command("spec")
    def spec_(board: Annotated[str, typer.Argument(help="ocr or aqa")]) -> None:
        """Print the spec points for a board, with the tags a bank uses.

        Example: staff quiz spec ocr
        """
        try:
            points = spec.load_taxonomy(board)
        except ValueError as exc:
            typer.secho(str(exc), fg="red", err=True)
            raise typer.Exit(1) from None
        unit = ""
        for p in points:
            if p.unit != unit:
                unit = p.unit
                typer.echo(unit)
            typer.echo(f"  {p.tag:<12} {p.title}")
