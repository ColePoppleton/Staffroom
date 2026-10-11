"""``staff``: the command-line face of Staffroom.

Built-in commands: ``staff list`` and ``staff new <tool>``. Every discovered plugin
gets a sub-app: ``staff <tool> <subcommand>``.

Help text is for a teacher: each command's docstring opens with one line that
says what it does, and ends with an ``Example:`` paragraph. ``_tidy_help``
joins hard-wrapped lines and drops reStructuredText quoting before typer
renders them, so ``staff --help`` reads as sentences.
"""

from __future__ import annotations

import functools
import inspect
import re
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any

import typer

from staffroom import __version__
from staffroom.core.config import Config, load_config
from staffroom.core.discovery import discover_plugins
from staffroom.core.log import setup_logging
from staffroom.core.plugin import ToolError, plugin_hidden
from staffroom.core.scaffold import scaffold_tool
from staffroom.library_cli import library_app

app = typer.Typer(
    name="staff",
    help=(
        "Staffroom: small tools for a computing teacher.\n\n"
        "Run staff COMMAND --help to see what a command does, with an example."
    ),
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)


_cli_config: Config | None = None
"""The config ``_root`` loaded for this invocation; ``_record_cli_run`` reads
its ``read_only`` flag. (click 8.5 no longer exposes the current context inside
a typer command, so this is not kept on ``ctx.obj``.)"""


@app.callback()
def _root(
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Also print the detailed log (for a bug report)"),
    ] = False,
) -> None:
    global _cli_config
    config = load_config()
    # The log file always gets the records; the terminal only with -v, since
    # each command already prints its own plain line for anything that matters.
    setup_logging("DEBUG" if verbose else config.general.log_level, stderr=verbose)
    _cli_config = config


HIDDEN_MARKER = "[hidden]"


@app.command("list")
def list_tools() -> None:
    """List the installed tools in sidebar order.

    Tools hidden from the launcher are marked; they still run from here.

    Example: staff list
    """
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


NEW_NEEDS_CHECKOUT = (
    "staff new only works in a clone of the Staffroom repository, and this copy is installed: "
    "fork and clone it (docs/contributing.md), then run just new <name> there."
)


@app.command("new")
def new_tool(
    name: Annotated[str, typer.Argument(help="Tool name: lowercase, digits, underscores")],
) -> None:
    """Scaffold a new tool package under src/staffroom/tools/ (in a checkout only)."""
    from staffroom.core import install

    if not install.detect().is_checkout:
        # An installed copy would write the tool into site-packages, where the
        # next update deletes it (#18). One line, no traceback.
        typer.secho(NEW_NEEDS_CHECKOUT, fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
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
    """Print the version of Staffroom you are running.

    Example: staff version
    """
    typer.echo(__version__)


@app.command("update")
def update_(
    check: Annotated[bool, typer.Option("--check", help="Only report; do not pull")] = False,
) -> None:
    """Update this copy of Staffroom to the latest release.

    Compares this copy with the released branch (origin/main, or release_branch in
    config.toml), then fast-forwards to it and syncs dependencies. It never switches
    branch or overwrites your edits. An installed copy runs no git: it prints the one
    command that updates it.

    Example: staff update --check
    """
    from staffroom.core import update

    st = update.status()
    typer.echo(st.describe())
    if check or not st.available:
        raise typer.Exit(0)
    if not st.on_release:
        release = st.remote.partition("/")[2]
        typer.echo(f"Not updating: this copy is {st.note}. Switch to {release} to update.")
        raise typer.Exit(0)
    try:
        typer.echo(update.apply())
    except (RuntimeError, OSError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None


@app.command("usage")
def usage_() -> None:
    """Show which tools you have used, how often, and when last.

    Counts launcher runs and staff commands together, then shows each one's share.
    Only tool names and dates are kept, on this Mac.

    Example: staff usage
    """
    from staffroom.core.usage import summary, usage_file

    rows = summary()
    if not rows:
        typer.echo(f"nothing recorded yet ({usage_file()})")
        return
    for u in rows:
        hosts = f"launcher {u.launcher_runs}, cli {u.cli_runs}"
        typer.echo(f"{u.name:<12} {u.runs:>4} run(s)   {hosts:<22}   last {u.last_used}")
    known = {p.name for p in discover_plugins()}
    unused = sorted(known - {u.name for u in rows})
    if unused:
        typer.echo("never run: " + ", ".join(unused))


app.add_typer(library_app, name="library")


def _record_cli_run(tool: str) -> None:
    """Count a finished ``staff <tool> ...`` command for ``staff usage``, the
    CLI's half of what the launcher's worker records. Skipped when the config is
    ``read_only`` (one-off runs that must persist nothing); a home folder that
    cannot be written is handled inside ``record_run`` and never fails the
    command. Only the tool's name and the date are stored."""
    from staffroom.core.usage import record_run

    if _cli_config is not None and _cli_config.read_only:
        return
    record_run(tool, source="cli")


def _guard_tool_command(tool: str, command: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap one of ``tool``'s commands so that, without each command repeating
    it: a ``ToolError`` (wrong file type, mistyped option) is a message for the
    teacher, printed in red with exit 1, while every other exception is a bug
    and keeps its traceback; and a command that completes, by returning or by
    exiting 0, is recorded as a run of ``tool``. Every command counts, not just
    ``run``: listing a tool's presets is still using the tool. A non-zero exit
    is not counted."""

    @functools.wraps(command)
    def guarded(*args: Any, **kwargs: Any) -> Any:
        try:
            result = command(*args, **kwargs)
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        except typer.Exit as exc:
            if exc.exit_code == 0:
                _record_cli_run(tool)
            raise
        _record_cli_run(tool)
        return result

    return guarded


def _mount_plugins() -> None:
    for plugin in discover_plugins():
        sub = typer.Typer(help=plugin.description, no_args_is_help=True)
        plugin.register_cli(sub)
        for info in sub.registered_commands:
            if info.callback is not None:
                info.callback = _guard_tool_command(plugin.name, info.callback)
        app.add_typer(sub, name=plugin.name)


_mount_plugins()


def tidy_help(text: str) -> str:
    """``text`` as typer should show it: paragraphs joined into single lines (rich
    markup keeps a docstring's hard wraps as forced breaks) and ``double
    backticks`` dropped. A paragraph starting with ``\\b`` keeps its breaks."""
    paragraphs = re.split(r"\n\s*\n", inspect.cleandoc(text))
    out = [p if p.startswith("\b") else " ".join(p.split()) for p in paragraphs]
    return "\n\n".join(out).replace("``", "")


def _tidy_help(typer_app: typer.Typer) -> None:
    """Apply ``tidy_help`` to every command and group under ``typer_app``."""
    for info in typer_app.registered_commands:
        doc = info.help or (info.callback.__doc__ if info.callback else None)
        if doc:
            info.help = tidy_help(doc)
    for group in typer_app.registered_groups:
        sub = group.typer_instance
        if sub is not None:
            _tidy_help(sub)


_tidy_help(app)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
