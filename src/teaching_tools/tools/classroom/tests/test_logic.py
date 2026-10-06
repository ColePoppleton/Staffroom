from datetime import date

import pytest

from teaching_tools.tools.classroom.logic import (
    label_folder,
    promoted_name,
    session_folder,
    summarise_diff,
    unified_diff,
    validate_label,
)


def test_validate_label() -> None:
    assert validate_label("  P3   Y9 loops ") == "P3 Y9 loops"
    with pytest.raises(ValueError, match="short label"):
        validate_label("   ")
    with pytest.raises(ValueError, match="one short line"):
        validate_label("x" * 61)
    with pytest.raises(ValueError, match="one short line"):
        validate_label("line one\nline two")


def test_label_folder_and_session_folder() -> None:
    assert label_folder("P3 Y9 loops") == "P3 Y9 loops"
    assert label_folder("P3: Y9/loops?") == "P3 Y9loops"
    assert label_folder("///") == "lesson"
    assert session_folder(date(2026, 10, 6), "P3 Y9 loops") == "2026-10-06/P3 Y9 loops"


@pytest.mark.parametrize(
    ("name", "existing", "expected"),
    [
        ("while.py", set(), "while_v2.py"),
        ("while.py", {"while_v2.py"}, "while_v3.py"),
        ("while_v2.py", set(), "while_v3.py"),
        ("while_v2.py", {"while_v3.py", "while_v4.py"}, "while_v5.py"),
        ("notes", set(), "notes_v2"),
        ("a.b.py", set(), "a.b_v2.py"),
    ],
)
def test_promoted_name(name: str, existing: set[str], expected: str) -> None:
    assert promoted_name(name, existing) == expected
    assert expected not in existing


def test_unified_diff_and_summary() -> None:
    diff = unified_diff("a\nb\n", "a\nc\nd\n", "original/x.py", "session/x.py")
    assert diff.startswith("--- original/x.py")
    assert "-b" in diff and "+c" in diff and "+d" in diff
    assert summarise_diff(diff) == "+2 / -1 lines"
    same = unified_diff("a\n", "a\n", "o", "s")
    assert same.startswith("No changes")
    assert summarise_diff(same) == "no changes"
