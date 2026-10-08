import pytest

from staffroom.core.table import Table
from staffroom.tools.hello.logic import Options, add_total, question_columns


def test_question_columns_match_prefix_and_digits() -> None:
    assert question_columns(["q1", "Q2", "q10", "quiz", "Total"], "q") == ["q1", "Q2", "q10"]


def test_add_total_appends_column_and_keeps_marker() -> None:
    table = Table(["q1", "q2"], [[4, 6], [2, None]], fake_data=True)
    result = add_total(table)
    assert result.columns == ["q1", "q2", "Total"]
    assert result.column("Total") == [10, 2]
    assert result.fake_data is True
    assert table.columns == ["q1", "q2"]  # original untouched


def test_add_total_with_percent() -> None:
    table = Table(["q1", "q2"], [[4, 6]])
    result = add_total(table, Options(max_marks=40))
    assert result.column("Percent") == [25.0]


def test_add_total_no_question_columns() -> None:
    with pytest.raises(ValueError, match="No question columns"):
        add_total(Table(["mark"], [[5]]))
