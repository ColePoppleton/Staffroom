"""Pure logic for the hello tool. Tables in, tables out; no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field

from teaching_tools.core.table import Cell, Table


@dataclass
class Options:
    forename_column: str = field(default="Forename", metadata={"label": "Forename column"})
    surname_column: str = field(default="Surname", metadata={"label": "Surname column"})
    uppercase: bool = field(default=True, metadata={"label": "Uppercase initials"})
    separator: str = field(
        default="", metadata={"label": "Separator", "help": "Put between initials, e.g. '.'"}
    )


def initials(forename: Cell, surname: Cell, options: Options) -> str:
    """``("Ada", "Lovelace") -> "AL"``; hyphenated and multi-part names
    contribute one letter per part, so ``"Mary-Jane"`` gives ``"MJ"``."""
    parts: list[str] = []
    for name in (forename, surname):
        for word in str(name or "").replace("-", " ").split():
            parts.append(word[0])
    text = options.separator.join(parts)
    return text.upper() if options.uppercase else text


def add_initials(table: Table, options: Options | None = None) -> Table:
    """Return ``table`` with an ``Initials`` column appended.

    Raises ``KeyError`` naming the missing column if the configured forename or
    surname column is absent.
    """
    options = options or Options()
    table.index_of(options.forename_column)
    table.index_of(options.surname_column)
    return table.with_column(
        "Initials",
        lambda row: initials(row[options.forename_column], row[options.surname_column], options),
    )
