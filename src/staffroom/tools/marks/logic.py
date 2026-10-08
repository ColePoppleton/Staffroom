"""Pure logic for marks: class-level analysis of raw marks. No I/O.

Input is a table with one column per question (``q1``, ``q2``, … ``Q3a``)
and one row per script. There are no pupils here: identifier columns are
dropped before the data arrives (``core.privacy``), and nothing per row is
ever written out by the tool.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from staffroom.core.table import Cell, Row, Table

QUESTION_RE = re.compile(r"^q\d+[a-z]?$", re.IGNORECASE)
MAX_FLAG = "MAX"
Unit = Literal["percent", "raw"]


@dataclass
class Options:
    unit: Unit = field(
        default="percent",
        metadata={"label": "Boundary unit", "help": "Minimums as % of the paper or raw marks"},
    )
    max_marks: str = field(
        default="",
        metadata={
            "label": "Max marks",
            "help": "Per question, e.g. 4,6,8,6,10,6 (or one number for all). "
            "Leave empty to use a MAX row, else the highest mark seen.",
        },
    )
    worst_n: int = field(default=5, metadata={"label": "Worst questions", "min": 1, "max": 50})


@dataclass(frozen=True)
class Boundary:
    grade: str
    minimum: float  # raw marks


@dataclass
class Analysis:
    grades: Table  # per script: view only, never saved
    distribution: Table
    questions: Table
    worst: Table
    max_marks: dict[str, float]
    warnings: list[str] = field(default_factory=list)

    @property
    def total_max(self) -> float:
        return sum(self.max_marks.values())


# ---------------------------------------------------------------- columns and maxima
def question_columns(columns: list[str]) -> list[str]:
    return [c for c in columns if QUESTION_RE.match(c.strip())]


def as_mark(value: Cell) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return 0.0


def split_max_row(table: Table) -> tuple[Table, dict[str, float] | None]:
    """Remove the row flagged ``MAX`` (any cell equal to ``MAX``) and return
    its question values as max marks. Returns ``(table, None)`` if absent."""
    qcols = question_columns(table.columns)
    for i, row in enumerate(table.rows):
        if any(isinstance(c, str) and c.strip().upper() == MAX_FLAG for c in row):
            record = dict(zip(table.columns, row, strict=True))
            maxes = {q: as_mark(record[q]) for q in qcols}
            rest = Table(list(table.columns), [r for j, r in enumerate(table.rows) if j != i])
            rest.fake_data = table.fake_data
            rest.dropped_columns = list(table.dropped_columns)
            return rest, maxes
    return table, None


def parse_max_text(text: str, qcols: list[str]) -> dict[str, float] | None:
    """``"4,6,8"`` -> per question; ``"10"`` -> the same for every question."""
    parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    if not parts:
        return None
    values = [float(p) for p in parts]
    if len(values) == 1:
        return dict.fromkeys(qcols, values[0])
    if len(values) != len(qcols):
        msg = f"Max marks lists {len(values)} values but there are {len(qcols)} questions"
        raise ValueError(msg)
    return dict(zip(qcols, values, strict=True))


def observed_max(table: Table, qcols: list[str]) -> dict[str, float]:
    return {q: max((as_mark(v) for v in table.column(q)), default=0.0) for q in qcols}


# ---------------------------------------------------------------- totals and grades
def totals(table: Table, qcols: list[str]) -> list[float]:
    idx = [table.index_of(q) for q in qcols]
    return [sum(as_mark(row[i]) for i in idx) for row in table.rows]


def parse_boundaries(table: Table, unit: Unit, total_max: float) -> list[Boundary]:
    """Rows of (grade, minimum) -> boundaries in raw marks, highest first."""
    found: list[Boundary] = []
    for record in table.to_dicts():
        values = list(record.values())
        if len(values) < 2 or values[0] is None or values[1] is None:
            continue
        grade = str(values[0]).strip()
        minimum = as_mark(values[1])
        if unit == "percent":
            minimum = total_max * minimum / 100.0
        if grade:
            found.append(Boundary(grade, minimum))
    if not found:
        msg = "No grade boundaries: add at least one row of grade and minimum."
        raise ValueError(msg)
    return sorted(found, key=lambda b: b.minimum, reverse=True)


def grade_for(total: float, boundaries: list[Boundary]) -> str:
    for b in boundaries:
        if total >= b.minimum - 1e-9:
            return b.grade
    return "U"


def grade_rows(
    table: Table, qcols: list[str], maxes: dict[str, float], boundaries: list[Boundary]
) -> Table:
    total_max = sum(maxes.values())
    rows: list[Row] = []
    for row, total in zip(table.rows, totals(table, qcols), strict=True):
        record = dict(zip(table.columns, row, strict=True))
        pct = round(100.0 * total / total_max, 1) if total_max else 0.0
        rows.append([*(record[q] for q in qcols), total, pct, grade_for(total, boundaries)])
    return Table([*qcols, "Total", "Percent", "Grade"], rows)


def distribution(grades: list[str], order: list[str]) -> Table:
    n = len(grades)
    counts = {g: 0 for g in order}
    for g in grades:
        counts[g] = counts.get(g, 0) + 1
    rows: list[Row] = [[g, c, round(100.0 * c / n, 1) if n else 0.0] for g, c in counts.items()]
    return Table(["Grade", "Count", "Percent"], rows)


# ---------------------------------------------------------------- per question
def facility(table: Table, qcols: list[str], maxes: dict[str, float]) -> dict[str, float]:
    """Mean mark as a fraction of the max: 1.0 means everyone got full marks."""
    n = len(table)
    out: dict[str, float] = {}
    for q in qcols:
        mean = sum(as_mark(v) for v in table.column(q)) / n if n else 0.0
        out[q] = mean / maxes[q] if maxes[q] else 0.0
    return out


def discrimination(table: Table, qcols: list[str], maxes: dict[str, float]) -> dict[str, float]:
    """(mean of top third - mean of bottom third) / max, by total mark. Near
    0 means the question does not separate stronger from weaker scripts."""
    n = len(table)
    if n < 2:
        return dict.fromkeys(qcols, 0.0)
    k = max(1, n // 3)
    order = sorted(range(n), key=lambda i: totals(table, qcols)[i], reverse=True)
    top, bottom = order[:k], order[-k:]
    out: dict[str, float] = {}
    for q in qcols:
        col = [as_mark(v) for v in table.column(q)]
        diff = sum(col[i] for i in top) / k - sum(col[i] for i in bottom) / k
        out[q] = diff / maxes[q] if maxes[q] else 0.0
    return out


def question_analysis(table: Table, qcols: list[str], maxes: dict[str, float]) -> Table:
    fac = facility(table, qcols, maxes)
    disc = discrimination(table, qcols, maxes)
    n = len(table)
    rows: list[Row] = []
    for q in qcols:
        mean = sum(as_mark(v) for v in table.column(q)) / n if n else 0.0
        rows.append([q, maxes[q], r2(mean), r2(fac[q]), r2(disc[q]), _verdict(fac[q], disc[q])])
    return Table(["Question", "Max", "Mean", "Facility", "Discrimination", "Note"], rows)


def r2(value: float) -> float:
    """Round to 2 dp with halves going up (0.825 -> 0.83), as a teacher would."""
    return round(value + 1e-9, 2)


def _verdict(fac: float, disc: float) -> str:
    notes = []
    if fac < 0.4:
        notes.append("hard")
    elif fac > 0.85:
        notes.append("easy")
    if disc < 0.2:
        notes.append("weak discriminator")
    return ", ".join(notes)


def worst_questions(questions: Table, n: int = 5) -> Table:
    """Lowest facility first: the questions to reteach."""
    ranked = questions.sorted_by("Facility")
    return Table(list(ranked.columns), ranked.rows[:n])


# ---------------------------------------------------------------- the whole thing
def analyse(table: Table, boundaries: Table, options: Options | None = None) -> Analysis:
    options = options or Options()
    warnings: list[str] = []
    data, max_row = split_max_row(table)
    qcols = question_columns(data.columns)
    if not qcols:
        msg = f"No question columns (q1, q2, …) in {data.columns}"
        raise ValueError(msg)
    if not data.rows:
        msg = "No scripts: the file has a header and no marks."
        raise ValueError(msg)
    maxes = parse_max_text(options.max_marks, qcols)
    if maxes is None:
        maxes = max_row
    if maxes is None:
        maxes = observed_max(data, qcols)
        warnings.append(
            "No max marks given (no MAX row, no option): using the highest mark seen per question."
        )
    bounds = parse_boundaries(boundaries, options.unit, sum(maxes.values()))
    grades = grade_rows(data, qcols, maxes, bounds)
    order = [b.grade for b in bounds]
    if "U" not in order:
        order.append("U")
    dist = distribution([str(g) for g in grades.column("Grade")], order)
    questions = question_analysis(data, qcols, maxes)
    return Analysis(
        grades=grades,
        distribution=dist,
        questions=questions,
        worst=worst_questions(questions, options.worst_n),
        max_marks=maxes,
        warnings=warnings,
    )
