"""``tt library ...``: index, search and tag the resources folder."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from teaching_tools.core.config import load_config
from teaching_tools.core.library.model import Kind
from teaching_tools.core.library.service import LibraryService

library_app = typer.Typer(help="The Resource Library: index, search, tags.", no_args_is_help=True)


def _service() -> LibraryService:
    return LibraryService(Path(load_config().general.resources_root))


@library_app.command()
def index(
    full: Annotated[
        bool, typer.Option("--full", help="Re-extract every file, not just changed")
    ] = False,
) -> None:
    """Index (or incrementally re-index) the resources root."""
    svc = _service()
    if not svc.root_exists:
        typer.secho(f"resources root not found: {svc.root}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    typer.echo(f"indexing {svc.root}")

    def progress(done: int, total: int, rel: str) -> None:
        if rel and done % 50 == 0:
            typer.secho(f"  {done}/{total} {rel}", dim=True, err=True)

    stats = svc.index(full=full, progress=progress)
    typer.echo(stats.summary())


@library_app.command()
def search(
    query: Annotated[str, typer.Argument(help="Words to find in names or text")],
    kind: Annotated[list[str] | None, typer.Option("--kind", "-k", help="python, pdf, …")] = None,
    tag: Annotated[str | None, typer.Option("--tag", "-t")] = None,
    hidden: Annotated[bool, typer.Option("--hidden", help="Include hidden cruft")] = False,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 25,
) -> None:
    """Search file names and extracted text."""
    svc = _service()
    if svc.count() == 0:
        typer.secho("index is empty; run  tt library index", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(1)
    kinds = [k for k in (kind or []) if k]  # validated loosely; unknown kinds match nothing
    hits = svc.search(query, kinds=kinds or None, tag=tag, include_hidden=hidden, limit=limit)  # type: ignore[arg-type]
    if not hits:
        typer.echo("no matches")
        raise typer.Exit(0)
    for hit in hits:
        r = hit.resource
        flag = " (cloud-only)" if r.cloud_only else ""
        typer.echo(f"{r.kind:<9} {r.rel_path}{flag}")
        if hit.snippet:
            typer.secho(f"          {hit.snippet}", dim=True)
    typer.echo(f"{len(hits)} match{'es' if len(hits) != 1 else ''}")


@library_app.command()
def tags(
    path: Annotated[str, typer.Argument(help="Path relative to the resources root")],
    set_tags: Annotated[str | None, typer.Option("--set", help="Comma-separated tags")] = None,
    notes: Annotated[str | None, typer.Option("--notes")] = None,
) -> None:
    """Show or set the tags and notes for one resource."""
    svc = _service()
    rel = _relative(svc, path)
    if set_tags is not None or notes is not None:
        current = svc.tag_entry(rel)
        entry = svc.set_tags(
            rel,
            set_tags if set_tags is not None else current.tags,
            notes if notes is not None else current.notes,
        )
        typer.echo(f"saved to {svc.tags.path}")
    else:
        entry = svc.tag_entry(rel)
    typer.echo(f"{rel}\n  tags:  {', '.join(entry.tags) or '-'}\n  notes: {entry.notes or '-'}")


@library_app.command()
def status() -> None:
    """Where the root is and when it was last indexed."""
    svc = _service()
    last = svc.last_indexed()
    when = datetime.fromisoformat(last).astimezone().strftime("%Y-%m-%d %H:%M") if last else "never"
    typer.echo(f"root:        {svc.root} ({'exists' if svc.root_exists else 'MISSING'})")
    typer.echo(f"database:    {svc.db.path}")
    typer.echo(f"files:       {svc.count()}")
    typer.echo(f"last index:  {when}")
    typer.echo(f"tags file:   {svc.tags.path} ({len(svc.tags.all_tags())} tags)")


def _relative(svc: LibraryService, path: str) -> str:
    p = Path(path).expanduser()
    if p.is_absolute():
        try:
            return p.resolve().relative_to(svc.root).as_posix()
        except ValueError:
            typer.secho(f"{p} is not under {svc.root}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
    return Path(path).as_posix()


_ = Kind  # re-exported for type checkers
