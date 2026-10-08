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
#: Grade column of the extra distribution row that counts scripts with a blank
#: or non-numeric cell. It is not a grade: leave it out of the chart.
INCOMPLETE_LABEL = "Incomplete scripts"
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
    incomplete_scripts: int = 0  # scripts with at least one blank or non-numeric cell

    @property
    def total_max(self) -> float:
        return sum(self.max_marks.values())


# ---------------------------------------------------------------- columns and maxima
def question_columns(columns: list[str]) -> list[str]:
    return [c for c in columns if QUESTION_RE.match(c.strip())]


def mark_or_none(value: Cell) -> float | None:
    """A numeric mark, or ``None`` for a blank or non-numeric cell such as
    ``ab`` (absent) or ``-``. Blanks count as 0 in a script's total but are
    left out of facility and discrimination, where a 0 would mean "attempted
    and got nothing"."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def as_mark(value: Cell) -> float:
    mark = mark_or_none(value)
    return 0.0 if mark is None else mark


def _mean(values: list[float | None]) -> float:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else 0.0


def split_max_row(table: Table) -> tuple[Table, dict[str, float] | None]:
    """Remove the row flagged ``MAX`` and return its question values as max
    marks. Returns ``(table, None)`` if absent.

    A row counts if any cell equals ``MAX`` or if the reader flagged it
    (``Table.flagged_rows``): a markbook export puts ``MAX`` in the name
    column, which is dropped before the table reaches this tool, so the
    decision is made in ``core.csvio`` on the raw file and only the row index
    arrives here."""
    qcols = question_columns(table.columns)
    flagged = set(table.flagged_rows)
    for i, row in enumerate(table.rows):
        if i in flagged or any(isinstance(c, str) and c.strip().upper() == MAX_FLAG for c in row):
            record = dict(zip(table.columns, row, strict=True))
            maxes = {q: as_mark(record[q]) for q in qcols}
            rest = Table(list(table.columns), [r for j, r in enumerate(table.rows) if j != i])
            rest.fake_data = table.fake_data
            rest.dropped_columns = list(table.dropped_columns)
            rest.flagged_rows = [j - (j > i) for j in table.flagged_rows if j != i]
            return rest, maxes
    return table, None


def parse_max_text(text: str, qcols: list[str]) -> dict[str, float] | None:
    """``"4,6,8"`` -> per question; ``"10"`` -> the same for every question."""
    parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    if not parts:
        return None
    try:
        values = [float(p) for p in parts]
    except ValueError:
        bad = next(p for p in parts if not _is_number(p))
        msg = f"Max marks should be numbers like 4,6,8 (one per question) or 10, not {bad!r}."
        raise ValueError(msg) from None
    if len(values) == 1:
        return dict.fromkeys(qcols, values[0])
    if len(values) != len(qcols):
        msg = f"Max marks lists {len(values)} values but there are {len(qcols)} questions"
        raise ValueError(msg)
    return dict(zip(qcols, values, strict=True))


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def observed_max(table: Table, qcols: list[str]) -> dict[str, float]:
    return {q: max((as_mark(v) for v in table.column(q)), default=0.0) for q in qcols}


# ---------------------------------------------------------------- sanity checks
def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def check_marks(table: Table, qcols: list[str], maxes: dict[str, float]) -> tuple[list[str], int]:
    """Warnings a teacher needs before trusting the numbers, and how many
    scripts have a blank or non-numeric cell. Nothing here stops the run."""
    warnings: list[str] = []
    blanks: dict[str, int] = {}
    incomplete = 0
    for row in table.rows:
        record = dict(zip(table.columns, row, strict=True))
        missing = [q for q in qcols if mark_or_none(record[q]) is None]
        for q in missing:
            blanks[q] = blanks.get(q, 0) + 1
        incomplete += bool(missing)
    for q in qcols:
        if maxes[q] <= 0:
            warnings.append(
                f"{q} has a max of 0: its facility and discrimination are reported as 0. "
                "Check the MAX row or the Max marks option."
            )
            continue
        over = [m for m in (mark_or_none(v) for v in table.column(q)) if m is not None]
        over = [m for m in over if m > maxes[q] + 1e-9]
        if over:
            warnings.append(
                f"{q}: {_plural(len(over), 'script')} scored above the max of {maxes[q]:g} "
                f"(highest {max(over):g}). Check the marks or the max."
            )
    if blanks:
        detail = ", ".join(f"{q}: {blanks[q]}" for q in qcols if q in blanks)
        warnings.append(
            f"{_plural(sum(blanks.values()), 'blank or non-numeric cell')} ({detail}) counted as 0 "
            "in totals and left out of facility and discrimination; "
            f"{incomplete} of {len(table)} scripts incomplete."
        )
    return warnings, incomplete


def check_boundaries(boundaries: list[Boundary], total_max: float) -> list[str]:
    """Warn when a boundary is above the paper total, which is what applying a
    percent preset with the unit set to raw marks looks like."""
    above = [b for b in boundaries if b.minimum > total_max + 1e-9]
    if not above:
        return []
    top = above[0]
    noun = "1 grade boundary is" if len(above) == 1 else f"{len(above)} grade boundaries are"
    return [
        f"{noun} above the paper total of {total_max:g} (highest: {top.grade} at "
        f"{top.minimum:g} marks), so no script can reach them. "
        "Check the boundary unit (percent or raw)."
    ]


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


def distribution(grades: list[str], order: list[str], incomplete: int = 0) -> Table:
    """Count per grade. With ``incomplete`` > 0 a last row (:data:`INCOMPLETE_LABEL`)
    says how many scripts had a blank or non-numeric cell; those scripts are
    also counted under their grade, so the row is a note, not a grade."""
    n = len(grades)
    counts = {g: 0 for g in order}
    for g in grades:
        counts[g] = counts.get(g, 0) + 1
    rows: list[Row] = [[g, c, round(100.0 * c / n, 1) if n else 0.0] for g, c in counts.items()]
    if incomplete:
        rows.append([INCOMPLETE_LABEL, incomplete, round(100.0 * incomplete / n, 1) if n else 0.0])
    return Table(["Grade", "Count", "Percent"], rows)


def without_incomplete_row(dist: Table) -> Table:
    """The distribution with the incomplete-scripts note removed, for the chart."""
    return Table(list(dist.columns), [r for r in dist.rows if r[0] != INCOMPLETE_LABEL])


# ---------------------------------------------------------------- per question
def facility(table: Table, qcols: list[str], maxes: dict[str, float]) -> dict[str, float]:
    """Mean mark as a fraction of the max: 1.0 means everyone got full marks.
    Blank and non-numeric cells are left out of the mean."""
    out: dict[str, float] = {}
    for q in qcols:
        mean = _mean([mark_or_none(v) for v in table.column(q)])
        out[q] = mean / maxes[q] if maxes[q] > 0 else 0.0
    return out


def discrimination(table: Table, qcols: list[str], maxes: dict[str, float]) -> dict[str, float]:
    """(mean of top third - mean of bottom third) / max, by total mark. Near
    0 means the question does not separate stronger from weaker scripts."""
    n = len(table)
    if n < 2:
        return dict.fromkeys(qcols, 0.0)
    k = max(1, n // 3)
    tot = totals(table, qcols)
    order = sorted(range(n), key=lambda i: tot[i], reverse=True)
    top, bottom = order[:k], order[-k:]
    out: dict[str, float] = {}
    for q in qcols:
        col = [mark_or_none(v) for v in table.column(q)]
        diff = _mean([col[i] for i in top]) - _mean([col[i] for i in bottom])
        out[q] = diff / maxes[q] if maxes[q] > 0 else 0.0
    return out


def question_analysis(table: Table, qcols: list[str], maxes: dict[str, float]) -> Table:
    fac = facility(table, qcols, maxes)
    disc = discrimination(table, qcols, maxes)
    rows: list[Row] = []
    for q in qcols:
        mean = _mean([mark_or_none(v) for v in table.column(q)])
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
    checks, incomplete = check_marks(data, qcols, maxes)
    warnings.extend(checks)
    bounds = parse_boundaries(boundaries, options.unit, sum(maxes.values()))
    warnings.extend(check_boundaries(bounds, sum(maxes.values())))
    grades = grade_rows(data, qcols, maxes, bounds)
    order = [b.grade for b in bounds]
    if "U" not in order:
        order.append("U")
    dist = distribution([str(g) for g in grades.column("Grade")], order, incomplete)
    questions = question_analysis(data, qcols, maxes)
    return Analysis(
        grades=grades,
        distribution=dist,
        questions=questions,
        worst=worst_questions(questions, options.worst_n),
        max_marks=maxes,
        warnings=warnings,
        incomplete_scripts=incomplete,
    )
