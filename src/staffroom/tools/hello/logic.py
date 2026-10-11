"""Pure logic for the hello tool. Tables in, tables out; no I/O.

What comes out is class-level: one row per question, never one per script,
so nothing a run saves can be traced back to a row of the input."""

from __future__ import annotations

from dataclasses import dataclass, field

from staffroom.core.table import Cell, Table

COLUMNS = ["Question", "Answered", "Mean", "Highest"]


@dataclass
class Options:
    prefix: str = field(
        default="q", metadata={"label": "Question column prefix", "help": "e.g. q for q1, q2…"}
    )


def question_columns(columns: list[str], prefix: str) -> list[str]:
    """Columns named ``<prefix><digits>``, case-insensitive: ``q1``, ``Q12``."""
    p = prefix.lower()
    return [c for c in columns if c.lower().startswith(p) and c[len(p) :].isdigit()]


def summarise(table: Table, options: Options | None = None) -> Table:
    """One row per question: how many scripts have a mark for it, the mean
    and the highest mark. Raises ``ValueError`` if no column matches the
    prefix."""
    options = options or Options()
    questions = question_columns(table.columns, options.prefix)
    if not questions:
        msg = f"No question columns starting with {options.prefix!r} in {table.columns}"
        raise ValueError(msg)
    rows: list[list[Cell]] = []
    for question in questions:
        marks = [
            m
            for m in table.column(question)
            if isinstance(m, int | float) and not isinstance(m, bool)
        ]
        mean = round(sum(marks) / len(marks), 1) if marks else None
        rows.append([question, len(marks), mean, max(marks, default=None)])
    return Table(list(COLUMNS), rows, fake_data=table.fake_data)
