from pathlib import Path

import pytest

from teaching_tools.core.csvio import (
    FAKE_DATA_MARKER,
    has_fake_data_marker,
    read_table,
    write_table,
)
from teaching_tools.core.table import Table


def test_read_example_strips_marker(example_marks: Path) -> None:
    t = read_table(example_marks)
    assert t.fake_data is True
    assert t.columns == ["q1", "q2", "q3", "q4", "q5", "q6"]
    assert len(t) == 10
    assert t.rows[0] == [4, 6, 7, 5, 9, 6]  # coerced to int


def test_csv_round_trip_keeps_marker(tmp_path: Path) -> None:
    t = Table(["a", "b"], [[1, None], ["x", 2.5]], fake_data=True)
    out = write_table(t, tmp_path / "out.csv")
    assert out.read_text().splitlines()[0] == FAKE_DATA_MARKER
    assert read_table(out) == t
    assert has_fake_data_marker(out)


def test_csv_without_marker(tmp_path: Path) -> None:
    p = tmp_path / "real.csv"
    p.write_text("a,b\n1,2\n")
    assert read_table(p).fake_data is False
    assert not has_fake_data_marker(p)


def test_xlsx_round_trip(tmp_path: Path) -> None:
    t = Table(["topic", "mark"], [["loops", 9], ["lists", 10]], fake_data=True)
    out = write_table(t, tmp_path / "out.xlsx")
    back = read_table(out)
    assert back == t
    assert has_fake_data_marker(out)
    write_table(Table(["a"], [[1]]), tmp_path / "plain.xlsx")
    assert not has_fake_data_marker(tmp_path / "plain.xlsx")


def test_unsupported_suffix(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsupported"):
        read_table(tmp_path / "x.txt")
