from pathlib import Path

import pytest
from typer.testing import CliRunner

from staffroom import __version__
from staffroom.cli import app

runner = CliRunner()


def test_list_shows_hello() -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    assert any(line.startswith("hello") for line in result.output.splitlines())
    assert "reference tool" in result.output
    assert "Total" in result.output


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
