from pathlib import Path

import pytest

from teaching_tools.core.csvio import read_table, write_table
from teaching_tools.core.privacy import drop_identifier_columns, is_identifier_column
from teaching_tools.core.table import Table


@pytest.mark.parametrize(
    "header",
    [
        "Name",
        "Forename",
        "SURNAME",
        "First name",
        "firstName",
        "Full_Name",
        "Pupil",
        "Student ID",
        "studentid",
        "ID",
        "UPN",
        "Candidate Number",
        "Cand No",
        "Email",
        "E-mail address",
        "Class",
        "Form",
        "Tutor Group",
        "Reg Group",
        "Set",
        "Adno",
        "Admission Number",
        "DOB",
        "Date of Birth",
        "Initials",
    ],
)
def test_identifier_headers(header: str) -> None:
    assert is_identifier_column(header)


@pytest.mark.parametrize(
    "header", ["q1", "Q12", "Total", "Percent", "classwork", "Mark", "max", "Grade", "", "Topic"]
)
def test_non_identifier_headers(header: str) -> None:
    assert not is_identifier_column(header)


def test_drop_identifier_columns() -> None:
    table = Table(["Name", "q1", "Class", "q2"], [["x", 1, "y", 2]], fake_data=True)
    clean, dropped = drop_identifier_columns(table)
    assert dropped == ["Name", "Class"]
    assert clean.columns == ["q1", "q2"]
    assert clean.rows == [[1, 2]]
    assert clean.fake_data is True
    assert clean.dropped_columns == ["Name", "Class"]
    assert table.columns == ["Name", "q1", "Class", "q2"]  # untouched


def test_nothing_to_drop_returns_same_table() -> None:
    table = Table(["q1"], [[1]])
    clean, dropped = drop_identifier_columns(table)
    assert clean is table and dropped == []


def test_read_table_always_drops(tmp_path: Path) -> None:
    csv = tmp_path / "with_ids.csv"
    csv.write_text("Candidate Number,q1,q2\n1001,3,4\n")
    table = read_table(csv)
    assert table.columns == ["q1", "q2"]
    assert table.dropped_columns == ["Candidate Number"]
    xlsx = write_table(Table(["email", "q1"], [["a@b", 5]]), tmp_path / "ids.xlsx")
    assert read_table(xlsx).columns == ["q1"]
