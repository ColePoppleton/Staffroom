from pathlib import Path

import pytest

from staffroom.core.csvio import (
    FAKE_DATA_MARKER,
    has_fake_data_marker,
    read_table,
    write_table,
)
from staffroom.core.plugin import ToolError
from staffroom.core.table import Table


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


# Input mistakes are teacher messages (ToolError), not tracebacks (#14). Each
# message names the file and says what would have worked.
def test_unsupported_suffix_is_a_teacher_message(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hello")
    with pytest.raises(ToolError, match=r"notes\.txt.*\.csv.*\.xlsx") as info:
        read_table(tmp_path / "notes.txt")
    assert "ValueError" not in str(info.value) and "\n" not in str(info.value)
    with pytest.raises(ToolError, match="no file extension"):
        read_table(tmp_path / "notes")


def test_missing_file_is_a_teacher_message(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match=r"Could not find gone\.csv"):
        read_table(tmp_path / "gone.csv")


def test_binary_file_named_csv_is_a_teacher_message(tmp_path: Path) -> None:
    # An xlsx renamed to .csv: bytes that are not UTF-8 text.
    write_table(Table(["a"], [[1]]), tmp_path / "book.xlsx")
    fake_csv = tmp_path / "book.csv"
    fake_csv.write_bytes((tmp_path / "book.xlsx").read_bytes())
    with pytest.raises(ToolError, match=r"book\.csv.*not a plain CSV"):
        read_table(fake_csv)


def test_damaged_xlsx_is_a_teacher_message(tmp_path: Path) -> None:
    (tmp_path / "renamed.xlsx").write_text("a,b\n1,2\n")  # a CSV renamed to .xlsx
    with pytest.raises(ToolError, match=r"renamed\.xlsx.*not really an Excel file"):
        read_table(tmp_path / "renamed.xlsx")
    (tmp_path / "truncated.xlsx").write_bytes(b"PK\x03\x04 not a workbook")
    with pytest.raises(ToolError, match=r"truncated\.xlsx"):
        read_table(tmp_path / "truncated.xlsx")
    # A real workbook still reads: the catch is narrow.
    assert read_table(write_table(Table(["a"], [[1]]), tmp_path / "ok.xlsx")).rows == [[1]]


def test_flag_rows_are_found_before_identifier_columns_are_dropped(tmp_path: Path) -> None:
    # A markbook export: the MAX flag sits in the name column, which the filter drops.
    p = tmp_path / "markbook.csv"
    p.write_text("# FAKE DATA\nSurname,Forename,q1,q2\nMAX,,4,6\ns1,f1,3,5\ns2,f2,4,6\n")
    t = read_table(p, flag="max")
    assert t.columns == ["q1", "q2"]  # the filter still ran, unconditionally
    assert t.dropped_columns == ["Surname", "Forename"]
    assert t.flagged_rows == [0]
    assert t.rows[0] == [4, 6]  # the flag cell itself did not come through
    assert read_table(p).flagged_rows == []  # no flag asked for, nothing recorded


def test_flag_rows_xlsx_and_whitespace(tmp_path: Path) -> None:
    src = Table(["Name", "q1"], [["x", 3], [" Max ", 4], ["y", 2]], fake_data=True)
    out = write_table(src, tmp_path / "book.xlsx")
    t = read_table(out, flag="MAX")
    assert t.columns == ["q1"] and t.flagged_rows == [1]
    assert read_table(out, flag="TOTAL").flagged_rows == []
