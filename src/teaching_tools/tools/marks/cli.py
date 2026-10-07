"""``tt marks ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from teaching_tools.core.config import load_config
from teaching_tools.core.paths import default_output_dir
from teaching_tools.core.plugin import RunContext, ToolError
from teaching_tools.tools.marks import presets
from teaching_tools.tools.marks.logic import Options

SourceArg = Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="CSV or XLSX")]


def register(app: typer.Typer) -> None:
    @app.command()
    def run(
        source: SourceArg,
        preset: Annotated[str, typer.Option("--preset", "-p", help="Boundary preset name")] = (
            presets.DEFAULT_PRESET
        ),
        unit: Annotated[str, typer.Option("--unit", help="percent or raw")] = "percent",
        max_marks: Annotated[str, typer.Option("--max", help="e.g. 4,6,8 or 10")] = "",
        worst: Annotated[int, typer.Option("--worst", help="How many worst questions")] = 5,
        out: Annotated[Path | None, typer.Option("--out", "-o", help="Output folder")] = None,
    ) -> None:
        """Grade SOURCE and save class-level aggregates (distribution, questions, chart)."""
        from teaching_tools.tools.marks import plugin

        config = load_config()
        available = presets.all_presets(config)
        if preset not in available:
            typer.secho(f"unknown preset {preset!r}; see  tt marks presets", fg="red", err=True)
            raise typer.Exit(1)
        if unit not in ("percent", "raw"):
            typer.secho("--unit must be percent or raw", fg="red", err=True)
            raise typer.Exit(1)
        ctx = RunContext(
            config=config,
            output_dir=out
            or default_output_dir(
                source, config.general.output_dir, resources_root=config.general.resources_root
            ),
            progress=lambda _f, msg: typer.secho(msg, dim=True, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        inputs = {
            "marks": source,
            "boundaries": presets.preset_table(available[preset]),
            "options": Options(unit=unit, max_marks=max_marks, worst_n=worst),  # type: ignore[arg-type]
        }
        try:
            result = plugin.run(inputs, ctx)
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        _print_table("Grade distribution", result.tables["distribution"])
        _print_table("Per-question analysis", result.tables["questions"])
        _print_table("Worst questions", result.tables["worst"])
        typer.echo(result.summary)
        for f in result.files:
            typer.echo(f"  {f}")

    @app.command("presets")
    def presets_() -> None:
        """List boundary presets (built-in and saved)."""
        config = load_config()
        saved = presets.saved_presets(config)
        for name, rows in presets.all_presets(config).items():
            kind = "saved" if name in saved else "built-in"
            typer.echo(f"{name}  ({kind}): " + ", ".join(f"{g}≥{m:g}" for g, m in rows))


def _print_table(title: str, table: object) -> None:
    from teaching_tools.core.table import Table

    assert isinstance(table, Table)
    typer.echo(f"\n{title}")
    widths = [
        max(len(str(c)), *(len(_fmt(r[i])) for r in table.rows))
        for i, c in enumerate(table.columns)
    ]
    typer.echo(
        "  " + "  ".join(str(c).ljust(w) for c, w in zip(table.columns, widths, strict=True))
    )
    for row in table.rows:
        typer.echo("  " + "  ".join(_fmt(v).ljust(w) for v, w in zip(row, widths, strict=True)))


def _fmt(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)
