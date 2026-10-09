"""``staff library ...``: index, search and tag the resources folder."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from staffroom.core.config import load_config
from staffroom.core.library.model import Kind, withheld_message
from staffroom.core.library.service import LibraryService

library_app = typer.Typer(
    help="The Resource Library: index, search, tags, exclusions.", no_args_is_help=True
)


def _service() -> LibraryService:
    general = load_config().general
    return LibraryService(Path(general.resources_root), exclude=general.library_exclude)


def _where_to_set_it() -> str:
    return (
        "choose it in Staffroom › Settings › Resources folder, or set resources_root "
        f"under [general] in {load_config().path}"
    )


def _require_root(svc: LibraryService) -> None:
    """Exit 1 with a sentence that says what to do when there is no usable
    folder: none chosen yet (a fresh install), or the chosen one is gone."""
    if svc.root_exists:
        return
    if not svc.root_set:
        message = f"no resources folder set yet: {_where_to_set_it()}"
    else:
        message = f"resources root not found: {svc.root} ({_where_to_set_it()})"
    typer.secho(message, fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


def _require_writable(svc: LibraryService) -> None:
    """Exit 1 with the reason when the database cannot be written (#65)."""
    if svc.unavailable_reason is None:
        return
    typer.secho(svc.unavailable_reason, fg=typer.colors.RED, err=True)
    typer.secho(svc.unavailable_detail(), dim=True, err=True)
    raise typer.Exit(1)


@library_app.command()
def index(
    full: Annotated[
        bool, typer.Option("--full", help="Re-extract every file, not just changed")
    ] = False,
) -> None:
    """Index (or incrementally re-index) the resources root."""
    svc = _service()
    _require_writable(svc)
    _require_root(svc)
    typer.echo(f"indexing {svc.root}")

    def progress(done: int, total: int, rel: str) -> None:
        if rel and done % 50 == 0:
            typer.secho(f"  {done}/{total} {rel}", dim=True, err=True)

    stats = svc.index(full=full, progress=progress)
    typer.echo(stats.summary())
    if stats.withheld_paths:
        for rel in stats.withheld_paths:
            typer.secho(f"  name only: {rel}", dim=True)
    if stats.excluded:
        typer.secho(f"{stats.excluded} exclusion pattern(s) in force", dim=True)


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
    if not svc.searchable:
        _require_writable(svc)  # "index is empty; run index" would send them nowhere
    if svc.counts().indexed == 0:
        _require_root(svc)  # a fresh install hears where the folder is set, not "empty"
        typer.secho("index is empty; run  staff library index", fg=typer.colors.YELLOW, err=True)
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
    if svc.root_set:
        typer.echo(f"root:        {svc.root} ({'exists' if svc.root_exists else 'MISSING'})")
    else:
        typer.echo(f"root:        (not set: {_where_to_set_it()})")
    typer.echo(f"database:    {svc.db.path}")
    if svc.unavailable_reason is not None:
        typer.secho(svc.unavailable_reason, fg=typer.colors.YELLOW)
        typer.secho(svc.unavailable_detail(), dim=True)
    counts = svc.counts()  # the one definition the sidebar and header use too (#30)
    typer.echo(f"files:       {counts.describe()}")
    typer.echo(f"last index:  {when}")
    typer.echo(f"tags file:   {svc.tags.path} ({len(svc.tags.all_tags())} tags)")
    excl = svc.exclusions()
    typer.echo(f"excluded:    {', '.join(excl.patterns) if excl else '-'}")
    typer.echo(
        f"ignore file: {svc.ignore_file} ({'present' if svc.ignore_file.exists() else 'none'})"
    )
    withheld = counts.name_only
    typer.echo(f"name only:   {withheld} file{'s' if withheld != 1 else ''}")
    if withheld:
        typer.secho(withheld_message(withheld), fg=typer.colors.YELLOW)
    typer.secho(
        "Stored: file names and the text of .py/.txt/.md/.csv/.pdf files only, in the database "
        "above. The resources folder is only read. Delete the database or change the root "
        "(a full re-index drops the old entries) to remove the index.",
        dim=True,
    )


@library_app.command()
def exclude(
    add: Annotated[
        list[str] | None,
        typer.Option("--add", "-a", help="Folder name, glob or path from the root to exclude"),
    ] = None,
    remove: Annotated[
        list[str] | None, typer.Option("--remove", "-r", help="Pattern to stop excluding")
    ] = None,
) -> None:
    """Show or change the exclusion list (folders the library never indexes or lists).

    Names match at any depth ("Pupil work", "*assessment*"); paths match from the
    root ("Year 11/Mocks"). Patterns in <root>/.staffroom/ignore are also honoured.
    Re-index afterwards: staff library index."""
    from staffroom.core.library.exclude import normalise_patterns

    cfg = load_config()
    patterns = list(cfg.general.library_exclude)
    changed = False
    for pattern in normalise_patterns(add or []):
        if pattern not in patterns:
            patterns.append(pattern)
            changed = True
    for pattern in normalise_patterns(remove or []):
        if pattern in patterns:
            patterns.remove(pattern)
            changed = True
        else:
            typer.secho(f"not in the list: {pattern}", fg=typer.colors.YELLOW, err=True)
    if changed:
        cfg.general.library_exclude = patterns
        try:
            cfg.save()
        except OSError as exc:
            typer.secho(
                f"cannot save {cfg.path}: {exc.strerror or exc}", fg=typer.colors.RED, err=True
            )
            raise typer.Exit(1) from None
        typer.echo(f"saved to {cfg.path}; run  staff library index  to apply")
    svc = LibraryService(Path(cfg.general.resources_root), exclude=patterns)
    typer.echo("configured:  " + (", ".join(patterns) or "-"))
    from_file = svc.ignore_file_patterns()
    typer.echo(f"ignore file: {', '.join(from_file) or '-'}  ({svc.ignore_file})")


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
