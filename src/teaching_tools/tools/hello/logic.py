"""Pure logic for the hello tool. Tables in, tables out; no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field

from teaching_tools.core.table import Cell, Table


@dataclass
class Options:
    prefix: str = field(
        default="q", metadata={"label": "Question column prefix", "help": "e.g. q for q1, q2…"}
    )
    max_marks: int = field(
        default=0,
        metadata={"label": "Paper total", "help": "If > 0, also add a Percent column", "min": 0},
    )


def question_columns(columns: list[str], prefix: str) -> list[str]:
    """Columns named ``<prefix><digits>``, case-insensitive: ``q1``, ``Q12``."""
    p = prefix.lower()
    return [c for c in columns if c.lower().startswith(p) and c[len(p) :].isdigit()]


def row_total(row: dict[str, Cell], columns: list[str]) -> int | float:
    total: int | float = 0
    for c in columns:
        value = row[c]
        if isinstance(value, int | float) and not isinstance(value, bool):
            total += value
    return total


def add_total(table: Table, options: Options | None = None) -> Table:
    """Append ``Total`` (and ``Percent`` when ``max_marks`` is set).

    Raises ``ValueError`` if no question columns match the prefix.
    """
    options = options or Options()
    qcols = question_columns(table.columns, options.prefix)
    if not qcols:
        msg = f"No question columns starting with {options.prefix!r} in {table.columns}"
        raise ValueError(msg)
    result = table.with_column("Total", lambda row: row_total(row, qcols))
    if options.max_marks > 0:
        result = result.with_column(
            "Percent", lambda row: round(100 * row_total(row, qcols) / options.max_marks, 1)
        )
    return result
