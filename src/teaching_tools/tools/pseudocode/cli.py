"""``tt pseudocode to-ocr | to-aqa | to-python <file>``."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from teaching_tools.core.config import load_config
from teaching_tools.core.paths import default_output_dir
from teaching_tools.core.plugin import RunContext, ToolError
from teaching_tools.tools.pseudocode.logic import Options

SourceArg = Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="Input file")]
SaveOpt = Annotated[bool, typer.Option("--save", help="Also write the translation to a file")]
FromOpt = Annotated[str, typer.Option("--from", help="python, ocr or aqa (default: from the file)")]
OutOpt = Annotated[Path | None, typer.Option("--out", "-o", help="Folder to write the translation")]


def _guess(source: Path, hint: str) -> str:
    if hint:
        return hint
    name = source.name.lower()
    if name.endswith(".py"):
        return "python"
    if ".aqa" in name:
        return "aqa"
    return "ocr"


def _run(source: Path, src: str, dst: str, out: Path | None, save: bool) -> None:
    from teaching_tools.tools.pseudocode import plugin

    if src not in ("python", "ocr", "aqa") or src == dst:
        typer.secho(f"cannot translate from {src!r} to {dst!r}", fg="red", err=True)
        raise typer.Exit(1)
    config = load_config()
    ctx = RunContext(
        config=config,
        output_dir=out
        or default_output_dir(
            source, config.general.output_dir, resources_root=config.general.resources_root
        ),
        log=lambda msg: typer.echo(msg, err=True),
    )
    options = Options(direction=f"{src}_to_{dst}", formats="txt" if save else "none")  # type: ignore[arg-type]
    try:
        result = plugin.run({"source": source, "options": options}, ctx)
    except ToolError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    typer.echo(result.texts["output"], nl=False)
    typer.echo("\n" + result.texts["report"], err=True)
    if result.files:
        typer.echo(result.summary, err=True)


def register(app: typer.Typer) -> None:
    @app.command("to-ocr")
    def to_ocr(
        source: SourceArg, from_: FromOpt = "", out: OutOpt = None, save: bool = False
    ) -> None:
        """Translate SOURCE (Python or AQA) to OCR Exam Reference Language."""
        _run(source, _guess(source, from_), "ocr", out, save)

    @app.command("to-aqa")
    def to_aqa(
        source: SourceArg, from_: FromOpt = "", out: OutOpt = None, save: bool = False
    ) -> None:
        """Translate SOURCE (Python or OCR) to AQA pseudocode."""
        _run(source, _guess(source, from_), "aqa", out, save)

    @app.command("to-python")
    def to_python(
        source: SourceArg, from_: FromOpt = "", out: OutOpt = None, save: bool = False
    ) -> None:
        """Translate SOURCE (OCR or AQA pseudocode) to Python."""
        _run(source, _guess(source, from_), "python", out, save)
