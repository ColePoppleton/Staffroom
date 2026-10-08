"""A tiny in-memory table: the lingua franca between tools, CSV/XLSX I/O and
the shell's table widgets. Deliberately not pandas: the data is small and the
type stays serialisable and trivially testable."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

Cell = str | int | float | bool | None
Row = list[Cell]


@dataclass
class Table:
    """Column names plus rows of cells.

    ``fake_data`` records whether the source carried the fake-data marker so
    that anything written back out keeps it (see :mod:`staffroom.core.csvio`).
    ``dropped_columns`` lists identifier columns removed at load time by
    :mod:`staffroom.core.privacy`; it is informational and not compared.
    ``flagged_rows`` holds the indices of rows that carried a flag word the
    reader was asked to look for (``csvio.read_table(path, flag="MAX")``),
    decided on the raw file before identifier columns were dropped. Only the
    yes/no decision travels; the cells it was made on do not.
    """

    columns: list[str]
    rows: list[Row] = field(default_factory=list)
    fake_data: bool = False
    dropped_columns: list[str] = field(default_factory=list, compare=False)
    flagged_rows: list[int] = field(default_factory=list, compare=False)

    def __post_init__(self) -> None:
        width = len(self.columns)
        for i, row in enumerate(self.rows):
            if len(row) != width:
                msg = f"row {i} has {len(row)} cells, expected {width}"
                raise ValueError(msg)

    # -- shape -----------------------------------------------------------
    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[Row]:
        return iter(self.rows)

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.rows), len(self.columns)

    def index_of(self, column: str) -> int:
        try:
            return self.columns.index(column)
        except ValueError:
            msg = f"no column named {column!r}; have {self.columns}"
            raise KeyError(msg) from None

    def column(self, name: str) -> list[Cell]:
        i = self.index_of(name)
        return [row[i] for row in self.rows]

    # -- conversion ------------------------------------------------------
    def to_dicts(self) -> list[dict[str, Cell]]:
        return [dict(zip(self.columns, row, strict=True)) for row in self.rows]

    @classmethod
    def from_dicts(
        cls, records: Iterable[Mapping[str, Cell]], columns: Sequence[str] | None = None
    ) -> Table:
        records = list(records)
        if columns is None:
            seen: dict[str, None] = {}
            for rec in records:
                for key in rec:
                    seen.setdefault(key, None)
            columns = list(seen)
        rows: list[Row] = [[rec.get(c) for c in columns] for rec in records]
        return cls(list(columns), rows)

    # -- transformation (all return new tables) ---------------------------
    def with_column(self, name: str, compute: Callable[[dict[str, Cell]], Cell]) -> Table:
        """Append a column whose value is computed from each row as a dict."""
        if name in self.columns:
            msg = f"column {name!r} already exists"
            raise ValueError(msg)
        new_rows: list[Row] = [
            [*row, compute(dict(zip(self.columns, row, strict=True)))] for row in self.rows
        ]
        return Table([*self.columns, name], new_rows, fake_data=self.fake_data)

    def select(self, columns: Sequence[str]) -> Table:
        idx = [self.index_of(c) for c in columns]
        return Table(list(columns), [[row[i] for i in idx] for row in self.rows], self.fake_data)

    def sorted_by(self, column: str, *, reverse: bool = False) -> Table:
        i = self.index_of(column)
        rows = sorted(self.rows, key=lambda r: (r[i] is None, r[i]), reverse=reverse)
        return Table(list(self.columns), rows, self.fake_data)


def coerce(value: Any) -> Cell:
    """Best-effort conversion of a raw text cell to int/float/bool, else str."""
    if value is None or isinstance(value, bool | int | float):
        return value
    text = str(value).strip()
    if text == "":
        return None
    lowered = text.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text
