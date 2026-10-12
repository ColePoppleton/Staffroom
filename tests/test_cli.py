from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

import staffroom.cli
from staffroom import __version__
from staffroom.cli import app
from staffroom.core.install import InstallKind

runner = CliRunner()


def test_list_shows_hello_marked_hidden_after_the_workflow_tools() -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    hello = next(line for line in lines if line.startswith("hello"))
    assert "reference tool" in hello and "per question" in hello and "[hidden]" in hello
    assert "[hidden]: not shown in the launcher" in result.output
    names = [line.split()[0] for line in lines if line and not line.startswith("[")]
    assert names[:3] == ["classroom", "worksheet", "quiz"]  # the sidebar's groups (#89)
    assert names.index("hello") > names.index("marks")
    assert sum("[hidden]" in line for line in lines) == 2  # hello's line and the legend


def test_hidden_tool_still_has_its_commands(example_marks: Path, tmp_path: Path) -> None:
    result = runner.invoke(app, ["hello", "run", str(example_marks), "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "marks_10x_summary.csv").exists()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.output.strip() == __version__


@pytest.mark.parametrize("kind", [InstallKind.UV_TOOL, InstallKind.OTHER])
def test_new_refuses_on_an_installed_copy(
    kind: InstallKind, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """From ``uv tool install`` (or pip, or a bundle) ``staff new`` would write
    into site-packages; it says so in one line and writes nothing (#18)."""
    from staffroom.core import install

    tools_dir = Path(staffroom.cli.__file__).resolve().parent / "tools"
    before = sorted(p.name for p in tools_dir.iterdir())
    package = tmp_path / "site-packages" / "staffroom"
    monkeypatch.setattr(install, "detect", lambda: install.Installation(kind, package))
    result = runner.invoke(app, ["new", "reading_age"])
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert lines == [staffroom.cli.NEW_NEEDS_CHECKOUT]
    assert "clone" in lines[0] and "installed" in lines[0]
    assert sorted(p.name for p in tools_dir.iterdir()) == before


def test_new_rejects_bad_name() -> None:
    result = runner.invoke(app, ["new", "Bad-Name"])
    assert result.exit_code == 1


def test_worksheet_cli_writes_nothing_to_cwd(
    isolated_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A tool with no input file and no configured output folder writes under
    the sessions root, not into whatever folder the command was run from."""
    isolated_home.mkdir(parents=True)
    sessions = tmp_path / "sessions"
    (isolated_home / "config.toml").write_text(f'[general]\nsessions_root = "{sessions}"\n')
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    result = runner.invoke(
        app, ["worksheet", "make", "-n", "2", "--format", "docx", "--no-preview"]
    )
    assert result.exit_code == 0, result.output
    assert list(cwd.iterdir()) == []
    written = list((sessions / "outputs" / "worksheet").glob("*.docx"))
    assert len(written) == 2, written
    assert str(sessions / "outputs" / "worksheet") in result.output


# ---------------------------------------------------------------- input mistakes (#14)
# A wrong file type or a mistyped option is a one-line message for the teacher,
# exit code 1, and never a traceback.
def _no_traceback(result: Result) -> None:
    for word in ("Traceback", "ValueError", "UnicodeDecodeError", "KeyError", "BadZipFile"):
        assert word not in result.output, result.output
    # CliRunner keeps an escaped exception here; a clean exit is None or SystemExit.
    assert result.exception is None or isinstance(result.exception, SystemExit), repr(
        result.exception
    )


@pytest.mark.parametrize("tool_cmd", [["hello", "run"], ["marks", "run"], ["hello", "preview"]])
def test_wrong_file_type_is_one_line(tmp_path: Path, tool_cmd: list[str]) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("just some notes\n")
    result = runner.invoke(app, [*tool_cmd, str(notes)])
    assert result.exit_code == 1, result.output
    _no_traceback(result)
    lines = [ln for ln in result.output.splitlines() if ln.strip()]
    assert len(lines) <= 2, result.output  # a progress line at most, then the message
    assert "notes.txt" in lines[-1] and ".csv" in lines[-1] and ".xlsx" in lines[-1]


def test_binary_csv_is_one_line(tmp_path: Path) -> None:
    from staffroom.core.csvio import write_table
    from staffroom.core.table import Table

    write_table(Table(["q1"], [[1]]), tmp_path / "book.xlsx")
    bad = tmp_path / "book.csv"
    bad.write_bytes((tmp_path / "book.xlsx").read_bytes())
    result = runner.invoke(app, ["hello", "run", str(bad), "--out", str(tmp_path)])
    assert result.exit_code == 1, result.output
    _no_traceback(result)
    assert "book.csv" in result.output and "not a plain CSV" in result.output


def test_fade_bad_ranges_says_what_was_expected(tmp_path: Path) -> None:
    src = tmp_path / "sol.py"
    src.write_text("x = 1\ny = 2\n")
    result = runner.invoke(
        app,
        ["fade", "make", str(src), "--order", "ranges", "--ranges", "abc", "--out", str(tmp_path)],
    )
    assert result.exit_code == 1, result.output
    _no_traceback(result)
    assert "Line ranges like 3-5, 8" in result.output and "'abc'" in result.output
    assert "invalid literal" not in result.output


def test_marks_bad_max_says_what_was_expected(tmp_path: Path, example_marks: Path) -> None:
    result = runner.invoke(
        app, ["marks", "run", str(example_marks), "--max", "4,6,x", "--out", str(tmp_path)]
    )
    assert result.exit_code == 1, result.output
    _no_traceback(result)
    assert "Max marks" in result.output and "'x'" in result.output
    assert "could not convert" not in result.output


def test_quiz_bad_date_says_what_was_expected(tmp_path: Path) -> None:
    from staffroom.core import paths

    examples = paths.examples_dir()
    log = tmp_path / "taught.csv"
    log.write_text("# FAKE DATA\ndate,topic\n2026-09-30,loops\n")
    result = runner.invoke(
        app,
        [
            "quiz",
            "retrieval",
            "--bank",
            str(examples / "question_bank.md"),
            "--log",
            str(log),
            "--date",
            "yesterday",
            "--out",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1, result.output
    _no_traceback(result)
    assert "yesterday" in result.output and "2026-10-08" in result.output
