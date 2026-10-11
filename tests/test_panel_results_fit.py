"""Results that fit the screen (#16), the GUI-free half: which columns a
fitted ResultsTable lifts and marks, and how a CardList reads its rows."""

from __future__ import annotations

import pytest

from staffroom.core.panel import (
    CardList,
    CodeSource,
    Constant,
    PanelSpec,
    ResultsTable,
    card_text,
    change_marks,
    constant_columns,
)
from staffroom.core.table import Table

# FAKE DATA: an invented trace of a five-score average (no people in it).
TRACE = Table(
    ["Line", "scores", "total", "average", "Output"],
    [
        [2, "[4, 6]", "", "", ""],
        [3, "[4, 6]", 0, "", ""],
        [5, "[4, 6]", 4, "", ""],
        [5, "[4, 6]", 10, "", ""],
        [6, "[4, 6]", 10, 5.0, ""],
        [7, "[4, 6]", 10, 5.0, "5.0"],
    ],
)


def test_a_value_that_repeats_down_the_table_is_lifted_with_its_line() -> None:
    found = constant_columns(TRACE, skip=("Line", "Output"), line_column="Line")
    assert found == [Constant("scores", "[4, 6]", 2)]


def test_a_value_set_near_the_end_stays_in_the_table() -> None:
    # average never changes once set, but on 2 of 6 rows its row says when it was set.
    names = [c.column for c in constant_columns(TRACE, skip=("Line",), line_column="Line")]
    assert "average" not in names and "total" not in names


def test_lifting_needs_two_rows_and_ignores_blanks_between() -> None:
    one = Table(["x"], [[1]])
    assert constant_columns(one) == []
    gaps = Table(["Line", "s"], [[1, "S"], [4, ""], [2, "S"], [5, ""]])  # a call in between
    assert constant_columns(gaps, line_column="Line") == [Constant("s", "S", 1)]
    assert constant_columns(gaps, skip=("Line",)) == [Constant("s", "S", None)]


def test_change_marks_bold_the_change_and_grey_the_carry() -> None:
    marks = change_marks(TRACE, skip=("Line", "Output"))
    total = TRACE.columns.index("total")
    assert [row[total] for row in marks] == [None, True, True, True, False, False]
    assert all(row[0] is None and row[-1] is None for row in marks)  # skipped columns
    assert marks[0][1] is True and marks[1][1] is False  # scores: set, then carried


def test_plain_columns_are_the_line_pinned_hidden_and_tag_columns() -> None:
    spec = ResultsTable("t", line_column="Line", pin_last=True, hidden_columns=("total",))
    assert spec.plain_columns(TRACE) == ("Line", "total", "Output")
    assert ResultsTable("t").plain_columns(TRACE) == ()


def test_card_text_fills_from_the_row_and_drops_a_blank_detail() -> None:
    record = {"Version": 2, "Line": 9, "Bug": "", "Changed to": "x = 1"}
    assert card_text("Version {Version}", record) == "Version 2"
    assert card_text("line {Line}", record) == "line 9"
    assert card_text("{Bug}", record) == ""
    assert card_text("{Changed to}", record) == "x = 1"  # a column name with a space
    assert card_text("{Missing}", record) == ""
    assert card_text("plain words", record) == "plain words"


def test_card_list_tones() -> None:
    spec = CardList("k", tones=(("crash", "danger"), ("wrong_output", "warning")))
    assert spec.tone("crash") == "danger"
    assert spec.tone("wrong_output") == "warning"
    assert spec.tone("silent") == "neutral" and spec.tone(None) == "neutral"


def test_a_card_list_must_point_at_a_code_source_of_its_panel() -> None:
    with pytest.raises(ValueError, match="CardList 'k' points its lines at 'source'"):
        PanelSpec(title="X", outputs=(CardList("k", line_column="Line"),))
    PanelSpec(
        title="X",
        inputs=(CodeSource(key="source"),),
        outputs=(CardList("k", line_column="Line"),),
    )
