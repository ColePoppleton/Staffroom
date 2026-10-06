"""Hand-checked numbers for examples/marks_10x_max.csv.

Max marks 4,6,8,6,10,6 (paper total 40). Totals per script:
37, 40, 30, 30, 37, 20, 31, 15, 36, 23. Column sums: q1 33, q2 46, q3 58,
q4 44, q5 75, q6 43 → means 3.3, 4.6, 5.8, 4.4, 7.5, 4.3.
"""

from pathlib import Path

import pytest

from teaching_tools.core.csvio import read_table
from teaching_tools.core.table import Table
from teaching_tools.tools.marks import logic
from teaching_tools.tools.marks.presets import BUILTIN_PRESETS, preset_table

OCR = preset_table(BUILTIN_PRESETS["OCR J277 (GCSE 9-1)"])


@pytest.fixture
def marks(example_marks_max: Path) -> Table:
    return read_table(example_marks_max)


def test_question_columns() -> None:
    assert logic.question_columns(["row", "q1", "Q2", "q10a", "quiz", "Total"]) == [
        "q1",
        "Q2",
        "q10a",
    ]


def test_split_max_row(marks: Table) -> None:
    data, maxes = logic.split_max_row(marks)
    assert maxes == {"q1": 4, "q2": 6, "q3": 8, "q4": 6, "q5": 10, "q6": 6}
    assert len(data) == 10 and data.fake_data
    assert logic.split_max_row(data) == (data, None)


def test_parse_max_text() -> None:
    q = ["q1", "q2", "q3"]
    assert logic.parse_max_text("", q) is None
    assert logic.parse_max_text("10", q) == {"q1": 10, "q2": 10, "q3": 10}
    assert logic.parse_max_text("4, 6; 8", q) == {"q1": 4, "q2": 6, "q3": 8}
    with pytest.raises(ValueError, match="2 values"):
        logic.parse_max_text("4,6", q)


def test_totals_and_facility(marks: Table) -> None:
    data, maxes = logic.split_max_row(marks)
    assert maxes is not None
    q = logic.question_columns(data.columns)
    assert logic.totals(data, q) == [37, 40, 30, 30, 37, 20, 31, 15, 36, 23]
    fac = logic.facility(data, q, maxes)
    assert fac["q1"] == pytest.approx(3.3 / 4)  # 0.825
    assert fac["q2"] == pytest.approx(4.6 / 6)  # 0.7667
    assert fac["q3"] == pytest.approx(5.8 / 8)  # 0.725
    assert fac["q4"] == pytest.approx(4.4 / 6)  # 0.7333
    assert fac["q5"] == pytest.approx(0.75)
    assert fac["q6"] == pytest.approx(4.3 / 6)  # 0.7167


def test_discrimination_top_vs_bottom_third(marks: Table) -> None:
    data, maxes = logic.split_max_row(marks)
    assert maxes is not None
    q = logic.question_columns(data.columns)
    disc = logic.discrimination(data, q, maxes)
    # top 3 by total: scripts 2, 1, 5 (40, 37, 37); bottom 3: 8, 6, 10 (15, 20, 23)
    assert disc["q1"] == pytest.approx((4 - (2 + 2 + 3) / 3) / 4)  # 0.4167
    assert disc["q5"] == pytest.approx(((10 + 9 + 9) / 3 - (4 + 5 + 6) / 3) / 10)  # 0.4333


def test_boundaries_and_grades(marks: Table) -> None:
    bounds = logic.parse_boundaries(OCR, "percent", 40)
    assert bounds[0] == logic.Boundary("9", 32.0) and bounds[-1] == logic.Boundary("U", 0.0)
    assert logic.grade_for(37, bounds) == "9"
    assert logic.grade_for(30, bounds) == "8"  # 75% ≥ 72%
    assert logic.grade_for(20, bounds) == "5"  # 50% ≥ 48%
    assert logic.grade_for(15, bounds) == "3"  # 37.5% ≥ 30%
    raw = logic.parse_boundaries(Table(["Grade", "Minimum"], [["A", 30], ["B", 20]]), "raw", 40)
    assert logic.grade_for(10, raw) == "U"
    with pytest.raises(ValueError, match="No grade boundaries"):
        logic.parse_boundaries(Table(["Grade", "Minimum"], []), "raw", 40)


def test_analyse_end_to_end(marks: Table) -> None:
    a = logic.analyse(marks, OCR)
    assert a.warnings == []
    assert a.total_max == 40
    assert a.grades.column("Grade") == ["9", "9", "8", "8", "9", "5", "8", "3", "9", "6"]
    assert a.grades.column("Percent")[7] == 37.5
    dist = {g: c for g, c, _ in a.distribution.rows}
    assert dist == {"9": 4, "8": 3, "7": 0, "6": 1, "5": 1, "4": 0, "3": 1, "2": 0, "1": 0, "U": 0}
    assert a.distribution.column("Percent")[0] == 40.0
    q = {row[0]: row for row in a.questions.rows}
    assert q["q1"][1:5] == [4, 3.3, 0.83, 0.42]
    assert q["q6"][3] == 0.72
    assert a.worst.column("Question") == ["q6", "q3", "q4", "q5", "q2"]  # lowest facility first


def test_analyse_without_max_row_warns_and_uses_observed(example_marks: Path) -> None:
    a = logic.analyse(read_table(example_marks), OCR)
    assert a.max_marks == {"q1": 4, "q2": 6, "q3": 8, "q4": 6, "q5": 10, "q6": 6}
    assert any("highest mark seen" in w for w in a.warnings)
    b = logic.analyse(read_table(example_marks), OCR, logic.Options(max_marks="4,6,8,6,10,6"))
    assert b.warnings == []


def test_analyse_errors() -> None:
    with pytest.raises(ValueError, match="No question columns"):
        logic.analyse(Table(["mark"], [[3]]), OCR)
    with pytest.raises(ValueError, match="No scripts"):
        logic.analyse(Table(["q1"], []), OCR)
