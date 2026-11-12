"""``staff addons ...``: list, install and remove the optional add-ons (#5).

The same plan and checks as Settings > Add-ons (:mod:`staffroom.core.addons`),
for a Terminal. Installing changes this copy of Staffroom; restart it
afterwards.
"""

from __future__ import annotations

from typing import Annotated

import typer

from staffroom.core import addons
from staffroom.core.discovery import discover_plugins
from staffroom.core.plugin import plugin_requires

addons_app = typer.Typer(
    help="Optional add-ons (web, media): list, install, remove.", no_args_is_help=True
)


def users(name: str) -> list[str]:
    """The tools that declare they require the add-on ``name``."""
    return [p.name for p in discover_plugins() if name in plugin_requires(p)]


@addons_app.command("list")
def list_() -> None:
    """List the add-ons, whether this copy has them, and which tools need them.

    Example: staff addons list
    """
    have = addons.installed()
    width = max(len(name) for name in addons.ADDONS)
    for name, addon in addons.ADDONS.items():
        state = "installed" if name in have else "not installed"
        typer.echo(f"{name:<{width}}  {state:<13}  {addon.enables}")
        tools = users(name)
        if tools:
            typer.echo(f"{'':<{width}}  {'':<13}  Used by: {', '.join(tools)}")
    typer.echo("\nInstall one with: staff addons install <name>")


def _name(name: str) -> str:
    if name not in addons.ADDONS:
        known = ", ".join(addons.ADDONS)
        typer.secho(f"no add-on called {name!r}; the add-ons are: {known}", fg="red", err=True)
        raise typer.Exit(2)
    return name


def _change(wanted: frozenset[str]) -> None:
    def show(line: str) -> None:
        typer.secho(line, dim=True, err=True)

    outcome = addons.change(wanted, log_line=show)
    if outcome.ok:
        typer.echo(outcome.message)
        return
    typer.secho(outcome.message, fg="red", err=True)
    if outcome.command:
        typer.echo(outcome.command)
    raise typer.Exit(1)


@addons_app.command()
def install(
    name: Annotated[str, typer.Argument(help="The add-on: web or media")],
) -> None:
    """Install an add-on into this copy of Staffroom, then restart it.

    Downloads it once (the Web add-on is a few hundred MB). A copy that cannot
    change itself prints the line to run instead.

    Example: staff addons install media
    """
    have = addons.installed()
    if _name(name) in have:
        typer.echo(f"{addons.get(name).sentence_label} is already installed.")
        return
    _change(have | {name})


@addons_app.command()
def remove(
    name: Annotated[str, typer.Argument(help="The add-on: web or media")],
) -> None:
    """Remove an add-on from this copy of Staffroom, then restart it.

    Example: staff addons remove media
    """
    have = addons.installed()
    if _name(name) not in have:
        typer.echo(f"{addons.get(name).sentence_label} is not installed.")
        return
    keeping = addons.included_in(name, have)
    if keeping is not None:
        label = addons.get(name).sentence_label
        typer.echo(f"{label} comes with {keeping.label}; remove that instead.")
        return
    _change(have - {name})
