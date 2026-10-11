import pytest

from staffroom.core.table import Table
from staffroom.tools.hello.logic import Options, question_columns, summarise


def test_question_columns_match_prefix_and_digits() -> None:
    assert question_columns(["q1", "Q2", "q10", "quiz", "Total"], "q") == ["q1", "Q2", "q10"]


def test_summarise_gives_one_row_per_question_not_per_script() -> None:
    table = Table(["q1", "q2"], [[3, 4], [1, None], [2, 0]], fake_data=True)
    result = summarise(table)
    assert result.columns == ["Question", "Answered", "Mean", "Highest"]
    assert result.rows == [["q1", 3, 2.0, 3], ["q2", 2, 2.0, 4]]
    assert result.fake_data is True
    assert table.columns == ["q1", "q2"]  # original untouched


def test_summarise_with_another_prefix() -> None:
    table = Table(["Mark1", "Mark2", "q1"], [[4, 6, 9]])
    assert [row[0] for row in summarise(table, Options(prefix="mark")).rows] == ["Mark1", "Mark2"]


def test_summarise_no_question_columns() -> None:
    with pytest.raises(ValueError, match="No question columns"):
        summarise(Table(["mark"], [[5]]))
