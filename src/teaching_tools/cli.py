"""``tt``: the command-line face of Teaching Tools.

Built-in commands: ``tt list`` and ``tt new <tool>``. Every discovered plugin
gets a sub-app: ``tt <tool> <subcommand>``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from teaching_tools import __version__
from teaching_tools.core.config import load_config
from teaching_tools.core.discovery import discover_plugins
from teaching_tools.core.log import setup_logging
from teaching_tools.core.scaffold import scaffold_tool
from teaching_tools.library_cli import library_app

app = typer.Typer(
    name="tt",
    help="Teaching Tools: small tools for a computing teacher.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


@app.callback()
def _root(
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging")] = False,
) -> None:
    config = load_config()
    setup_logging("DEBUG" if verbose else config.general.log_level)


@app.command("list")
def list_tools() -> None:
    """List installed tools."""
    plugins = discover_plugins()
    if not plugins:
        typer.echo("No tools installed. Create one with: tt new <name>")
        raise typer.Exit(0)
    width = max(len(p.name) for p in plugins)
    for p in plugins:
        typer.echo(f"{p.name:<{width}}  v{p.version:<7} {p.description}")


@app.command("new")
def new_tool(
    name: Annotated[str, typer.Argument(help="Tool name: lowercase, digits, underscores")],
) -> None:
    """Scaffold a new tool package under src/teaching_tools/tools/."""
    tools_dir = Path(__file__).resolve().parent / "tools"
    try:
        written = scaffold_tool(name, tools_dir)
    except (ValueError, FileExistsError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    for path in written:
        typer.echo(f"created {path.relative_to(tools_dir.parents[2])}")
    typer.echo(f"\nNext: edit logic.py, then run  tt {name} run examples/marks_10x.csv")


@app.command("version")
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


@app.command("usage")
def usage_() -> None:
    """Which tools have been used, how often, and when last (for the monthly review)."""
    from teaching_tools.core.usage import summary, usage_file

    rows = summary()
    if not rows:
        typer.echo(f"nothing recorded yet ({usage_file()})")
        return
    for u in rows:
        typer.echo(f"{u.name:<12} {u.runs:>4} run(s)   last {u.last_used}")
    known = {p.name for p in discover_plugins()}
    unused = sorted(known - {u.name for u in rows})
    if unused:
        typer.echo("never run: " + ", ".join(unused))


app.add_typer(library_app, name="library")


def _mount_plugins() -> None:
    for plugin in discover_plugins():
        sub = typer.Typer(help=plugin.description, no_args_is_help=True)
        plugin.register_cli(sub)
        app.add_typer(sub, name=plugin.name)


_mount_plugins()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
