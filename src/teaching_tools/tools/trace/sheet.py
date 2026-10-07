"""Trace tables as a house-style Document: code + blank table, key with the
completed table and the program's output."""

from __future__ import annotations

from datetime import date

from teaching_tools.core.codeinput import numbered_listing
from teaching_tools.core.export import Code, Document, Paragraph, TableBlock
from teaching_tools.core.table import Table


def build_document(
    name: str,
    source: str,
    blank: Table,
    completed: Table,
    stdout: str,
    *,
    truncated: bool,
    error: str | None,
    today: date | None = None,
) -> Document:
    doc = Document(
        title=f"Trace table: {name}",
        topic="Python",
        date=today or date.today(),
        subtitle=f"{len(completed)} steps" + (" (capped)" if truncated else ""),
    )
    sheet = doc.section()
    sheet.add(
        Paragraph(
            "Trace the program by hand. Each row is one executed line; write the value of "
            "every variable after that line has run, and anything it prints.",
            style="instruction",
        )
    )
    sheet.add(Code(numbered_listing(source), caption="Program"))
    sheet.add(TableBlock(tuple(blank.columns), _rows(blank), monospace=True))

    key = doc.section("Answer key", answers=True)
    key.add(TableBlock(tuple(completed.columns), _rows(completed), monospace=True))
    if stdout.strip():
        key.add(Code(stdout.rstrip("\n"), caption="Program output"))
    if error:
        key.add(Paragraph(f"The program ends with an error: {error}", style="muted"))
    if truncated:
        key.add(Paragraph("The trace was capped at the step limit.", style="muted"))
    return doc


def _rows(table: Table) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple("" if v is None else str(v) for v in row) for row in table.rows)
