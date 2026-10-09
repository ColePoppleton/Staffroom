"""Hand-checked numbers for examples/marks_10x_max.csv.

Max marks 4,6,8,6,10,6 (paper total 40). Totals per script:
37, 40, 30, 30, 37, 20, 31, 15, 36, 23. Column sums: q1 33, q2 46, q3 58,
q4 44, q5 75, q6 43 → means 3.3, 4.6, 5.8, 4.4, 7.5, 4.3.
"""

import random
import time
from pathlib import Path

import pytest

from staffroom.core.csvio import read_table
from staffroom.core.table import Table
from staffroom.tools.marks import logic
from staffroom.tools.marks.presets import BUILTIN_PRESETS, preset_table

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


# ---------------------------------------------------------------- sanity warnings (#12)
RAW_AB = Table(["Grade", "Minimum"], [["A", 8], ["B", 5]])


def test_split_max_row_uses_flag_decided_before_identifier_columns_were_dropped() -> None:
    # The MAX word lived in a dropped name column; only the row index survives.
    t = Table(["q1", "q2"], [[4, 6], [3, 5], [4, 6]], fake_data=True, flagged_rows=[0])
    data, maxes = logic.split_max_row(t)
    assert maxes == {"q1": 4, "q2": 6}
    assert data.rows == [[3, 5], [4, 6]] and data.fake_data
    assert data.flagged_rows == []


def test_mark_or_none_distinguishes_blank_and_text_from_zero() -> None:
    assert logic.mark_or_none(0) == 0.0
    assert logic.mark_or_none("3") == 3.0
    assert logic.mark_or_none(None) is None
    assert logic.mark_or_none("") is None
    assert logic.mark_or_none("ab") is None
    assert logic.mark_or_none(True) is None
    assert logic.as_mark("ab") == 0.0  # totals still count a blank as 0


def test_mark_above_max_warns_but_still_grades() -> None:
    t = Table(["row", "q1", "q2"], [["MAX", 5, 5], [1, 7, 3], [2, 5, 2], [3, 6, 1]])
    a = logic.analyse(t, RAW_AB, logic.Options(unit="raw"))
    assert a.warnings == [
        "q1: 2 scripts scored above the max of 5 (highest 7). Check the marks or the max."
    ]
    assert a.grades.column("Total") == [10, 7, 7]
    assert a.grades.column("Grade") == ["A", "B", "B"]
    assert a.grades.column("Percent")[0] == 100.0


def test_max_of_zero_warns_once() -> None:
    t = Table(["row", "q1", "q2"], [["MAX", 4, 0], [1, 3, 2], [2, 4, 0]])
    bounds = Table(["Grade", "Minimum"], [["A", 4], ["B", 2]])  # within the 4-mark total
    a = logic.analyse(t, bounds, logic.Options(unit="raw"))
    assert len(a.warnings) == 1  # the 2 > 0 marks on q2 are not reported twice
    assert a.warnings[0].startswith("q2 has a max of 0:")
    q = {row[0]: row for row in a.questions.rows}
    assert q["q2"][3] == 0.0 and q["q2"][4] == 0.0  # facility, discrimination reported as 0
    assert a.total_max == 4


def test_blank_and_text_cells_are_left_out_of_facility_and_counted() -> None:
    # q1: 4, blank, 2, ab -> mean of the two present marks is 3 (not 1.5 as if blanks were 0)
    # q2: 6, 3, ab, blank -> mean 4.5. Totals 10, 3, 2, 0; three of four scripts incomplete.
    t = Table(
        ["row", "q1", "q2"],
        [["MAX", 4, 6], [1, 4, 6], [2, None, 3], [3, 2, "ab"], [4, "ab", None]],
    )
    bounds = Table(["Grade", "Minimum"], [["A", 8], ["U", 0]])
    a = logic.analyse(t, bounds, logic.Options(unit="raw"))
    assert a.warnings == [
        "4 blank or non-numeric cells (q1: 2, q2: 2) counted as 0 in totals and left out of "
        "facility and discrimination; 3 of 4 scripts incomplete."
    ]
    assert a.incomplete_scripts == 3
    assert a.grades.column("Total") == [10, 3, 2, 0]
    q = {row[0]: row for row in a.questions.rows}
    assert q["q1"][2] == 3.0 and q["q1"][3] == 0.75
    assert q["q2"][2] == 4.5 and q["q2"][3] == 0.75
    # n=4 -> thirds of 1: top is script 1 (q1=4), bottom is script 4 (q1 blank -> no marks, 0)
    assert q["q1"][4] == 1.0
    assert a.distribution.rows == [
        ["A", 1, 25.0],
        ["U", 3, 75.0],
        [logic.INCOMPLETE_LABEL, 3, 75.0],
    ]
    assert logic.without_incomplete_row(a.distribution).rows == [["A", 1, 25.0], ["U", 3, 75.0]]


def test_boundaries_above_paper_total_warn(marks: Table) -> None:
    # The percent preset applied as raw marks: 80, 72, 64, 56, 48 are all above 40.
    a = logic.analyse(marks, OCR, logic.Options(unit="raw"))
    assert a.warnings == [
        "5 grade boundaries are above the paper total of 40 (highest: 9 at 80 marks), so no "
        "script can reach them. Check the boundary unit (percent or raw)."
    ]
    assert len(a.grades) == 10 and a.grades.column("Grade")[1] == "4"  # 40 marks -> grade 4


def test_clean_file_has_no_warnings(marks: Table) -> None:
    a = logic.analyse(marks, OCR)
    assert a.warnings == [] and a.incomplete_scripts == 0
    assert a.distribution.column("Grade")[-1] == "U"  # no incomplete row


# ---------------------------------------------------------------- whole-cohort size (#29)
def _cohort(rows: int, questions: int) -> Table:
    """A FAKE whole-cohort file: marks only, no identifiers, seeded so the
    numbers are the same on every run."""
    rng = random.Random(29)
    qcols = [f"q{i}" for i in range(1, questions + 1)]
    return Table(qcols, [[rng.randint(0, 4) for _ in qcols] for _ in range(rows)], fake_data=True)


def test_discrimination_computes_totals_once(monkeypatch: pytest.MonkeyPatch) -> None:
    # The O(n²) bug (#29) called totals() inside the sort key, once per script.
    calls = 0
    real_totals = logic.totals

    def counting_totals(table: Table, qcols: list[str]) -> list[float]:
        nonlocal calls
        calls += 1
        return real_totals(table, qcols)

    monkeypatch.setattr(logic, "totals", counting_totals)
    cohort = _cohort(rows=60, questions=5)
    qcols = logic.question_columns(cohort.columns)
    logic.discrimination(cohort, qcols, dict.fromkeys(qcols, 4.0))
    assert calls == 1


def test_analyse_whole_cohort_in_seconds_not_minutes() -> None:
    # Acceptance criterion for #29: 3,000 scripts x 30 questions in under 3 s.
    # It runs in about 0.15 s; the bound is loose so a busy CI runner passes,
    # and the old O(n²) code (about a minute) cannot.
    cohort = _cohort(rows=3000, questions=30)
    started = time.perf_counter()
    a = logic.analyse(cohort, RAW_AB, logic.Options(unit="raw", max_marks="4"))
    elapsed = time.perf_counter() - started
    assert elapsed < 3.0, f"analyse took {elapsed:.1f}s for 3,000 x 30"
    assert len(a.grades) == 3000 and len(a.questions) == 30
    assert all(-1.0 <= logic.as_mark(row[4]) <= 1.0 for row in a.questions.rows)  # discrimination


# ---------------------------------------------------------------- the report's headline (#87)
def test_headline_numbers_by_hand(marks: Table) -> None:
    # Totals 37, 40, 30, 30, 37, 20, 31, 15, 36, 23: sum 299 of 10 x 40.
    a = logic.analyse(marks, OCR)
    h = a.headline
    assert h.scripts == 10 and h.total_max == 40
    assert h.mean_total == pytest.approx(29.9)
    assert h.mean_percent == pytest.approx(74.75)
    # Sorted 15, 20, 23, 30, 30, 31, 36, 37, 37, 40: median (30 + 31) / 2 = 30.5 = 76.25% -> 8.
    assert h.median_total == 30.5 and h.median_grade == "8"
    # Grades 9, 9, 8, 8, 9, 5, 8, 3, 9, 6: all but the 3 are at grade 4 or above.
    assert h.pass_grade == "4" and h.at_or_above_pass == 9
    # Facility q6 0.717, q3 0.725, q4 0.733 are below the paper's 0.7475; q5 0.75 is not.
    assert h.reteach_below == pytest.approx(0.7475)  # = the mean %, with no blanks
    assert h.reteach == ["q6", "q3", "q4"]


def test_median_of_odd_and_even_counts() -> None:
    assert logic.median([3.0]) == 3.0
    assert logic.median([5.0, 1.0, 3.0]) == 3.0
    assert logic.median([4.0, 1.0, 3.0, 2.0]) == 2.5
    assert logic.median([]) == 0.0


def test_pass_grade_is_4_else_the_lowest_grade_above_zero() -> None:
    ocr = logic.parse_boundaries(OCR, "percent", 40)
    assert logic.pass_grade(ocr) == "4"
    a_level = logic.parse_boundaries(preset_table(BUILTIN_PRESETS["A-level (A*-E)"]), "percent", 40)
    assert logic.pass_grade(a_level) == "E"
    pass_fail = logic.parse_boundaries(
        Table(["Grade", "Minimum"], [["Pass", 50], ["Fail", 0]]), "percent", 40
    )
    assert logic.pass_grade(pass_fail) == "Pass"
    assert logic.pass_grade([logic.Boundary("U", 0.0)]) is None


def test_count_at_or_above_follows_the_boundary_order() -> None:
    order = ["9", "8", "7", "6", "5", "4", "3", "2", "1", "U"]
    assert logic.count_at_or_above(["9", "4", "3", "U", "5"], order, "4") == 3
    assert logic.count_at_or_above(["9", "4"], order, "missing") == 0


def test_reteach_is_below_the_paper_lowest_first_at_most_n() -> None:
    facility = {"q1": 0.9, "q2": 0.5, "q3": 0.6, "q4": 0.55, "q5": 0.8}
    assert logic.reteach(facility, overall=0.7, n=5) == ["q2", "q4", "q3"]
    assert logic.reteach(facility, overall=0.7, n=2) == ["q2", "q4"]
    assert logic.reteach(facility, overall=0.4, n=5) == []  # nothing below the paper
    assert logic.reteach({"a": 0.5, "b": 0.5}, overall=0.9, n=1) == ["a"]  # ties: paper order


def test_report_questions_hardest_first_with_reteach_marked(marks: Table) -> None:
    a = logic.analyse(marks, OCR)
    report = a.report_questions
    assert report.columns == ["Question", "Mean", "Facility", "Discr.", "Reteach", "Note"]
    assert report.column("Question") == ["q6", "q3", "q4", "q5", "q2", "q1"]
    assert report.column("Reteach") == ["reteach", "reteach", "reteach", "", "", ""]
    by_q = {row[0]: row for row in report.rows}
    assert by_q["q1"][1:4] == ["3.3 / 4", 0.83, 0.42]  # the same numbers as the saved CSV
    assert by_q["q5"][1] == "7.5 / 10"
    # The saved questions table keeps paper order and its columns.
    assert a.questions.column("Question") == ["q1", "q2", "q3", "q4", "q5", "q6"]
    assert a.questions.columns[-2:] == ["Discrimination", "Note"]


def test_headline_with_no_scripts_above_zero_max() -> None:
    t = Table(["row", "q1"], [["MAX", 0], [1, 0], [2, 0]])
    a = logic.analyse(t, RAW_AB, logic.Options(unit="raw"))
    assert a.headline.mean_percent == 0.0 and a.headline.reteach == []


# ---------------------------------------------------------------- load summary (#87)
def test_load_summary_of_a_clean_file(marks: Table) -> None:
    assert logic.load_summary(marks) == [
        (True, "10 scripts × 6 questions · MAX row found (paper out of 40)"),
        (True, "No identifier columns · ignored: row"),
    ]


def test_load_summary_without_max_row_and_with_dropped_columns(example_marks: Path) -> None:
    t = read_table(example_marks)
    t.dropped_columns = ["Name"]
    lines = logic.load_summary(t)
    assert lines[0] == (
        False,
        "10 scripts × 6 questions · no MAX row: set Max marks, or the highest mark seen is used",
    )
    assert lines[1] == (True, "Identifier column dropped, never used: Name")


def test_load_summary_of_a_file_with_no_questions() -> None:
    lines = logic.load_summary(Table(["mark", "total"], [[3, 4]]))
    assert lines == [(False, "No question columns (q1, q2, …): Analyse needs them")]


def test_a_question_with_a_max_of_0_is_never_tagged_for_reteaching(
    example_marks_messy: Path,
) -> None:
    # q3's MAX is 0: its facility is reported as 0 with a warning, not as "reteach".
    a = logic.analyse(read_table(example_marks_messy), OCR)
    assert "q3" not in a.headline.reteach
    by_q = {row[0]: row for row in a.report_questions.rows}
    assert by_q["q3"][4] == ""
    # Blanks are left out of facility, so the paper's facility leaves them out
    # too: q1 3.5/4, q2 4.33/6, q4 7.33/10 -> 15.17/20, not the mean total's 53%.
    assert a.headline.reteach_below == pytest.approx((3.5 + 13 / 3 + 22 / 3) / 20)
    assert a.headline.reteach == ["q2", "q4"]
