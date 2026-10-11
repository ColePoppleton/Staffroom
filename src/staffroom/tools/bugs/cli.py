"""``staff bugs ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.bugs.logic import KIND_LABELS, Options


def register(app: typer.Typer) -> None:
    @app.command()
    def make(
        source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="A .py file")],
        count: Annotated[int, typer.Option("--count", "-n")] = 4,
        seed: Annotated[int, typer.Option("--seed", "-s")] = 1,
        silent: Annotated[
            int,
            typer.Option(
                "--silent", help="Keep up to N bugs that leave the output unchanged (default 0)"
            ),
        ] = 0,
        kinds: Annotated[
            str, typer.Option("--kinds", help="Comma list; see  staff bugs kinds")
        ] = "",
        stdin: Annotated[str, typer.Option("--stdin", help="Inputs, use \\n between lines")] = "",
        fmt: Annotated[str, typer.Option("--format", "-f", help="both, docx or pdf")] = "both",
        out: Annotated[Path | None, typer.Option("--out", "-o")] = None,
        preview: Annotated[bool, typer.Option("--preview")] = False,
    ) -> None:
        """Write COUNT buggy copies of SOURCE plus a key saying what each one does."""
        from staffroom.tools.bugs import plugin

        options = Options(count=count, seed=seed, silent=silent, formats=fmt)  # type: ignore[arg-type]
        if kinds:
            wanted = {k.strip() for k in kinds.split(",")}
            unknown = wanted - set(KIND_LABELS)
            if unknown:
                typer.secho(f"unknown kinds: {', '.join(sorted(unknown))}", fg="red", err=True)
                raise typer.Exit(1)
            for k in KIND_LABELS:
                setattr(options, k, k in wanted)
        config = load_config()
        ctx = RunContext(
            config=config,
            output_dir=out or config.output_dir_for(source, "bugs"),
            progress=lambda _f, msg: typer.secho(msg, dim=True, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        try:
            result = plugin.run(
                {"source": source, "stdin": stdin.replace("\\n", "\n"), "options": options}, ctx
            )
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        table = result.tables["key"]
        for row in table.rows:
            typer.echo(f"  v{row[0]}  line {row[1]:<3} {row[2]:<28} {row[5]}")
        if preview:
            typer.echo(result.texts["preview"])
        typer.echo(result.summary)

    @app.command("kinds")
    def kinds_() -> None:
        """List the error classes."""
        for k, label in KIND_LABELS.items():
            typer.echo(f"{k:<18} {label}")
