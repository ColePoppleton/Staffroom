"""``staff classroom ...`` commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from staffroom.core import paths
from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext, ToolError


def _ctx() -> RunContext:
    config = load_config()
    return RunContext(
        config=config,
        output_dir=paths.sessions_root(config.general.sessions_root),
        log=lambda msg: typer.echo(msg, err=True),
    )


def _fail(exc: Exception) -> None:
    typer.secho(str(exc), fg=typer.colors.RED, err=True)
    raise typer.Exit(1) from None


def register(app: typer.Typer) -> None:
    @app.command("open")
    def open_(
        resource: Annotated[
            Path, typer.Argument(exists=True, dir_okay=False, help="File to teach from")
        ],
        label: Annotated[
            str, typer.Option("--label", "-l", help="Lesson label, e.g. 'P3 Y9 loops'")
        ],
    ) -> None:
        """Copy RESOURCE into today's session folder and open the copy in your editor."""
        from staffroom.tools.classroom import plugin

        try:
            result = plugin.run({"resource": resource, "label": label}, _ctx())
        except ToolError as exc:
            _fail(exc)
            return
        typer.echo(result.summary)
        typer.echo(str(result.files[0]))

    @app.command("list")
    def list_() -> None:
        """List past session copies (newest day first)."""
        from staffroom.tools.classroom import plugin

        ctx = _ctx()
        table = plugin.act("refresh", {}, ctx).tables["sessions"]
        typer.echo(f"sessions folder: {plugin.sessions_root(ctx)}")
        if not table.rows:
            typer.echo("no sessions yet")
            return
        for row in table.rows:
            typer.echo(f"{row[0]}  {row[1]:<24} {row[2]:<32} edited {row[3]}")

    @app.command()
    def diff(
        session_file: Annotated[str, typer.Argument(help="Path under the sessions folder")],
    ) -> None:
        """Unified diff of a session copy against its original."""
        from staffroom.tools.classroom import plugin

        try:
            result = plugin.act("diff", {"Session file": session_file}, _ctx())
        except ToolError as exc:
            _fail(exc)
            return
        typer.echo(result.texts["diff"])

    @app.command()
    def promote(
        session_file: Annotated[str, typer.Argument(help="Path under the sessions folder")],
    ) -> None:
        """Copy an edited session file back next to its original as <name>_v2.

        Never overwrites. An unchanged copy writes nothing and says which file already holds it.
        """
        from staffroom.tools.classroom import plugin

        try:
            result = plugin.act("promote", {"Session file": session_file}, _ctx())
        except ToolError as exc:
            _fail(exc)
            return
        typer.echo(result.summary)
        for written in result.files:
            typer.echo(str(written))

    @app.command()
    def reopen(
        session_file: Annotated[str, typer.Argument(help="Path under the sessions folder")],
    ) -> None:
        """Launch the editor on a session copy again."""
        from staffroom.tools.classroom import plugin

        try:
            result = plugin.act("reopen", {"Session file": session_file}, _ctx())
        except ToolError as exc:
            _fail(exc)
            return
        typer.echo(result.summary)
