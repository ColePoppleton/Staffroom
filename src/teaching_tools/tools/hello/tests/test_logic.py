import pytest

from teaching_tools.core.table import Table
from teaching_tools.tools.hello.logic import Options, add_initials, initials


def test_initials_basic() -> None:
    assert initials("Ada", "Lovelace", Options()) == "AL"


def test_initials_hyphen_and_double_barrel() -> None:
    assert initials("Mary-Jane", "Smith Jones", Options()) == "MJSJ"


def test_initials_options() -> None:
    assert initials("ada", "lovelace", Options(uppercase=False, separator=".")) == "a.l"


def test_add_initials_appends_column_and_keeps_marker() -> None:
    table = Table(["Forename", "Surname"], [["Ada", "Lovelace"], ["Alan", None]], fake_data=True)
    result = add_initials(table)
    assert result.columns == ["Forename", "Surname", "Initials"]
    assert result.column("Initials") == ["AL", "A"]
    assert result.fake_data is True
    assert table.columns == ["Forename", "Surname"]  # original untouched


def test_add_initials_missing_column() -> None:
    with pytest.raises(KeyError, match="Surname"):
        add_initials(Table(["Forename"], [["Ada"]]))
