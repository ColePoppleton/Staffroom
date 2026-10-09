from datetime import date

import pytest

from staffroom.tools.classroom.logic import (
    is_day_folder,
    is_session_folder,
    label_folder,
    latest_version,
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


@pytest.mark.parametrize(
    ("name", "existing", "expected"),
    [
        ("while.py", set(), None),
        ("while.py", {"while.py", "while_v2.py"}, "while_v2.py"),
        ("while.py", {"while_v2.py", "while_v3.py", "while_v10.py"}, "while_v10.py"),
        ("while_v2.py", {"while_v2.py", "while_v3.py"}, "while_v3.py"),
        ("while_v2.py", {"while_v2.py"}, None),  # only itself: nothing promoted yet
        ("while.py", {"whilst_v2.py", "while_v2.txt", "while_v2"}, None),  # other files
        ("notes", {"notes_v2", "notes_v3.py"}, "notes_v2"),
    ],
)
def test_latest_version(name: str, existing: set[str], expected: str | None) -> None:
    assert latest_version(name, existing) == expected


def test_unified_diff_and_summary() -> None:
    diff = unified_diff("a\nb\n", "a\nc\nd\n", "original/x.py", "session/x.py")
    assert diff.startswith("--- original/x.py")
    assert "-b" in diff and "+c" in diff and "+d" in diff
    assert summarise_diff(diff) == "+2 / -1 lines"
    same = unified_diff("a\n", "a\n", "o", "s")
    assert same.startswith("No changes")
    assert summarise_diff(same) == "no changes"


def test_is_day_folder() -> None:
    assert is_day_folder("2026-10-06")
    assert not is_day_folder("outputs")
    assert not is_day_folder("2026-13-01")  # shaped like a date, but not one
    assert not is_day_folder("2026-1-6")
    assert not is_day_folder("2026-10-06 copy")
    assert not is_day_folder(".2026-10-06")


@pytest.mark.parametrize(
    ("rel", "is_dir", "has_origin", "expected"),
    [
        # A real session: a date-named day folder, a label folder with .origin.json.
        ("2026-10-06/P3 Y9 loops", True, True, True),
        # The shared fallback output folder for tools (#97), even if it held a sidecar.
        ("outputs/worksheet", True, False, False),
        ("outputs/worksheet", True, True, False),
        # A stray file, at the root or inside a day folder.
        ("notes.txt", False, False, False),
        ("2026-10-06/notes.txt", False, False, False),
        # A folder the teacher made by hand that is not a day.
        ("Spare/P3 Y9 loops", True, True, False),
        # A day folder whose label folder classroom never made.
        ("2026-10-06/scratch", True, False, False),
        # Hidden folders and anything deeper than <day>/<label>.
        ("2026-10-06/.cache", True, True, False),
        ("2026-10-06", True, False, False),
        ("2026-10-06/P3 Y9 loops/sub", True, True, False),
    ],
)
def test_is_session_folder(rel: str, is_dir: bool, has_origin: bool, expected: bool) -> None:
    assert is_session_folder(rel, is_dir=is_dir, has_origin=has_origin) is expected
