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
