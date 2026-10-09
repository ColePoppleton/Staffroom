"""Phase 1b acceptance: the original stays byte-identical, diff shows the
edit, promote creates a new file the library picks up on re-index."""

from collections.abc import Callable, Sequence
from datetime import date
from pathlib import Path

import pytest

from staffroom.core.library.service import LibraryService
from staffroom.tools.classroom import sessions

Runner = Callable[[Sequence[str]], None]


@pytest.fixture
def runs() -> list[list[str]]:
    return []


@pytest.fixture
def runner(runs: list[list[str]]) -> Runner:
    return lambda argv: runs.append(list(argv))


def test_open_for_class_copies_and_launches(
    resources_root: Path, tmp_path: Path, runs: list[list[str]], runner: Runner
) -> None:
    original = resources_root / "Python" / "Python_Course" / "while_loops.py"
    before = original.read_bytes()
    root = tmp_path / "sessions"
    copy, created = sessions.open_for_class(
        original,
        "P3 Y9 loops",
        root,
        "open -a Thonny {file}",
        today=date(2026, 10, 6),
        runner=runner,
    )
    assert created
    assert copy == root / "2026-10-06" / "P3 Y9 loops" / "while_loops.py"
    assert copy.read_bytes() == before
    assert runs == [["open", "-a", "Thonny", str(copy)]]

    # Edit the copy "in Thonny"; the original is untouched byte for byte.
    copy.write_text(copy.read_text() + "print('done')\n")
    assert original.read_bytes() == before

    # Opening again for the same lesson re-opens the edited copy, no overwrite.
    copy2, created2 = sessions.open_for_class(
        original,
        "P3 Y9 loops",
        root,
        "open -a Thonny {file}",
        today=date(2026, 10, 6),
        runner=runner,
    )
    assert copy2 == copy and not created2
    assert "print('done')" in copy.read_text()
    assert len(runs) == 2


def test_list_diff_promote_reopen(
    resources_root: Path,
    tmp_path: Path,
    service: LibraryService,
    runs: list[list[str]],
    runner: Runner,
) -> None:
    original = resources_root / "Python" / "OCR Booklet" / "exercise_3a.py"
    root = tmp_path / "sessions"
    copy, _ = sessions.open_for_class(
        original, "P5 Y10 while", root, "open {file}", today=date(2026, 10, 6), runner=runner
    )
    copy.write_text(copy.read_text().replace("'yes'", "'y'"))

    listed = sessions.list_sessions(root)
    assert [f.rel_path for f in listed] == ["2026-10-06/P5 Y10 while/exercise_3a.py"]
    assert listed[0].label == "P5 Y10 while" and listed[0].origin == str(original.resolve())
    table = sessions.sessions_table(listed)
    assert table.columns[-1] == "Session file"

    diff = sessions.diff_against_original(copy)
    assert "-while answer != 'yes':" in diff and "+while answer != 'y':" in diff

    first = sessions.promote(copy, resources_root)
    assert first.created and first.target == original.parent / "exercise_3a_v2.py"
    assert first.target.read_text() == copy.read_text()
    assert original.read_text() != copy.read_text()  # original untouched
    assert first.summary == "Promoted as exercise_3a_v2.py next to the original"

    # Promoting the same unchanged copy again writes nothing and says so (#32).
    again = sessions.promote(copy, resources_root)
    assert not again.created and again.target == first.target
    assert again.summary == "Already promoted as exercise_3a_v2.py: the copy has not changed since"
    assert not (original.parent / "exercise_3a_v3.py").exists()

    # A further edit promotes as v3; v2 is left alone (never overwrites).
    copy.write_text(copy.read_text() + "print('bye')\n")
    third = sessions.promote(copy, resources_root)
    assert third.created and third.target.name == "exercise_3a_v3.py"
    assert "print('bye')" not in first.target.read_text()

    stats = service.index()
    assert stats.added == 2
    assert "Python/OCR Booklet/exercise_3a_v2.py" in [
        h.resource.rel_path for h in service.search("3a")
    ]

    argv = sessions.reopen(copy, "python3 -m idlelib {file}", runner)
    assert argv == ["python3", "-m", "idlelib", str(copy)] and runs[-1] == argv


def test_promote_unchanged_copy_writes_nothing(
    resources_root: Path, tmp_path: Path, runner: Runner
) -> None:
    original = resources_root / "Python" / "Python_Course" / "while_loops.py"
    before = sorted(p.name for p in original.parent.iterdir())
    copy, _ = sessions.open_for_class(
        original,
        "P3 Y9 loops",
        tmp_path / "s",
        "open {file}",
        today=date(2026, 10, 6),
        runner=runner,
    )
    outcome = sessions.promote(copy, resources_root)
    assert not outcome.created and outcome.matches_original and outcome.target == original
    assert outcome.summary.startswith("No changes: the copy matches the original while_loops.py")
    assert sorted(p.name for p in original.parent.iterdir()) == before  # nothing written

    # The compare is against the *latest* version: an edit equal to v2 while v3 exists
    # is a new version, because v3 is what the library would open.
    copy.write_text("# v2\n")
    v2 = sessions.promote(copy, resources_root)
    copy.write_text("# v3\n")
    v3 = sessions.promote(copy, resources_root)
    assert (v2.target.name, v3.target.name) == ("while_loops_v2.py", "while_loops_v3.py")
    copy.write_text("# v2\n")
    back = sessions.promote(copy, resources_root)
    assert back.created and back.target.name == "while_loops_v4.py"


def test_diff_and_promote_without_origin(tmp_path: Path) -> None:
    stray = tmp_path / "sessions" / "2026-10-06" / "x" / "stray.py"
    stray.parent.mkdir(parents=True)
    stray.write_text("x")
    assert "No origin recorded" in sessions.diff_against_original(stray)
    with pytest.raises(ValueError, match="No origin"):
        sessions.promote(stray, tmp_path)
    assert sessions.list_sessions(tmp_path / "nope") == []
    with pytest.raises(FileNotFoundError):
        sessions.resolve_session_file(tmp_path / "sessions", "2026-10-06/x/missing.py")


def test_label_is_validated(resources_root: Path, tmp_path: Path, runner: Runner) -> None:
    original = resources_root / "Python" / "notes.md"
    with pytest.raises(ValueError, match="short label"):
        sessions.open_for_class(original, "  ", tmp_path, "open {file}", runner=runner)
