"""``staff``: the command-line face of Staffroom.

Built-in commands: ``staff list`` and ``staff new <tool>``. Every discovered plugin
gets a sub-app: ``staff <tool> <subcommand>``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from staffroom import __version__
from staffroom.core.config import load_config
from staffroom.core.discovery import discover_plugins
from staffroom.core.log import setup_logging
from staffroom.core.plugin import plugin_hidden
from staffroom.core.scaffold import scaffold_tool
from staffroom.library_cli import library_app

app = typer.Typer(
    name="staff",
    help="Staffroom: small tools for a computing teacher.",
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


HIDDEN_MARKER = "[hidden]"


@app.command("list")
def list_tools() -> None:
    """List installed tools in sidebar order; hidden ones (not in the launcher) are marked."""
    plugins = discover_plugins()
    if not plugins:
        typer.echo("No tools installed. Create one with: staff new <name>")
        raise typer.Exit(0)
    width = max(len(p.name) for p in plugins)
    for p in plugins:
        marker = f"  {HIDDEN_MARKER}" if plugin_hidden(p) else ""
        typer.echo(f"{p.name:<{width}}  v{p.version:<7} {p.description}{marker}")
    if any(plugin_hidden(p) for p in plugins):
        typer.echo(f"\n{HIDDEN_MARKER}: not shown in the launcher; still runs from the CLI.")


@app.command("new")
def new_tool(
    name: Annotated[str, typer.Argument(help="Tool name: lowercase, digits, underscores")],
) -> None:
    """Scaffold a new tool package under src/staffroom/tools/."""
    tools_dir = Path(__file__).resolve().parent / "tools"
    try:
        written = scaffold_tool(name, tools_dir)
    except (ValueError, FileExistsError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    for path in written:
        typer.echo(f"created {path.relative_to(tools_dir.parents[2])}")
    typer.echo(f"\nNext: edit logic.py, then run  staff {name} run examples/marks_10x.csv")


@app.command("version")
def version() -> None:
    """Print the version."""
    typer.echo(__version__)


@app.command("update")
def update_(
    check: Annotated[bool, typer.Option("--check", help="Only report; do not pull")] = False,
) -> None:
    """Pull the latest code from the git remote and sync dependencies."""
    from staffroom.core import update

    st = update.status()
    typer.echo(st.describe())
    if check or not st.available:
        raise typer.Exit(0)
    try:
        typer.echo(update.apply())
    except (RuntimeError, OSError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None


@app.command("usage")
def usage_() -> None:
    """Which tools have been used, how often, and when last (for the monthly review)."""
    from staffroom.core.usage import summary, usage_file

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
