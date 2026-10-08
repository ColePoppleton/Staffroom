from pathlib import Path

import pytest
from typer.testing import CliRunner

from staffroom import __version__
from staffroom.cli import app

runner = CliRunner()


def test_list_shows_hello_marked_hidden_after_the_workflow_tools() -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    hello = next(line for line in lines if line.startswith("hello"))
    assert "reference tool" in hello and "Total" in hello and "[hidden]" in hello
    assert "[hidden]: not shown in the launcher" in result.output
    names = [line.split()[0] for line in lines if line and not line.startswith("[")]
    assert names[:2] == ["classroom", "marks"]
    assert names.index("hello") > names.index("pseudocode")
    assert sum("[hidden]" in line for line in lines) == 2  # hello's line and the legend


def test_hidden_tool_still_has_its_commands(example_marks: Path, tmp_path: Path) -> None:
    result = runner.invoke(app, ["hello", "run", str(example_marks), "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "marks_10x_totals.csv").exists()


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.output.strip() == __version__


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
