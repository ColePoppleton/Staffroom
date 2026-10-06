from typer.testing import CliRunner

from teaching_tools import __version__
from teaching_tools.cli import app

runner = CliRunner()


def test_list_shows_hello() -> None:
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    assert result.output.startswith("hello")
    assert "reference tool" in result.output


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.output.strip() == __version__


def test_new_rejects_bad_name() -> None:
    result = runner.invoke(app, ["new", "Bad-Name"])
    assert result.exit_code == 1
