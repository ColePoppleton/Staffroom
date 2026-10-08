from pathlib import Path

import pytest

from staffroom.core.csvio import read_table, write_table
from staffroom.core.privacy import drop_identifier_columns, is_identifier_column
from staffroom.core.table import Table


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


# ---------------------------------------------------------------- free text
@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("Candidate number: 4021", "candidate number"),
        ("candidate no 400123", "candidate number"),
        ("CANDIDATE ID = 9001", "candidate number"),
        ("UPN: A123456789012", "UPN"),
        ("upn 123456789", "UPN"),
        ("ULN: 1234567890", "ULN"),
        ("Admission number 12345", "admission number"),
        ("Adm No: 4567", "admission number"),
        ("Date of birth: 01/09/2009", "date of birth"),
        ("DOB 1.9.09", "date of birth"),
        ("Surname: Redacted", "surname"),
        ("last name - Withheld", "surname"),
        ("Forename: Anon", "forename"),
        ("Pupil name: Someone", "pupil name"),
        ("Student Name = Anybody", "pupil name"),
        ("email: someone@example.com", "email address"),
        ("E-mail address: a.b@school.example", "email address"),
    ],
)
def test_find_identifier_text_positive(text: str, label: str) -> None:
    from staffroom.core.privacy import find_identifier_text, looks_like_pupil_details

    assert label in find_identifier_text("# header\n" + text + "\nprint(1)\n")
    assert looks_like_pupil_details(text)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "while count < 10:\n    print(count)\n",
        "# Candidate number: ________\n# Surname: ________",  # blank template
        "Write a program that asks for the candidate number and prints it.",
        "The surname field should be validated for length.",
        "Date of birth is a common field in a database design task.",
        "UPN stands for Unique Pupil Number.",
        "email = input('Enter an email: ')",
        "forename = row[0]  # read the forename column",
        "candidate_number = int(input())",
    ],
)
def test_find_identifier_text_negative(text: str) -> None:
    from staffroom.core.privacy import find_identifier_text

    assert find_identifier_text(text) == []


def test_find_identifier_text_reports_each_label_once() -> None:
    from staffroom.core.privacy import find_identifier_text

    text = "Candidate number: 1111\nCandidate number: 2222\nUPN: 999999\nSurname: Redacted"
    assert find_identifier_text(text) == ["candidate number", "UPN", "surname"]
