from pathlib import Path

from typer.testing import CliRunner

from teaching_tools.cli import app
from teaching_tools.core.csvio import read_csv

runner = CliRunner()


def test_hello_run_writes_output(tmp_path: Path, example_class_list: Path) -> None:
    result = runner.invoke(app, ["hello", "run", str(example_class_list), "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    out = tmp_path / "class_list_with_initials.csv"
    assert out.exists()
    table = read_csv(out)
    assert "Initials" in table.columns
    assert table.fake_data is True


def test_hello_preview(example_class_list: Path) -> None:
    result = runner.invoke(app, ["hello", "preview", str(example_class_list), "--rows", "2"])
    assert result.exit_code == 0, result.output
    assert "Forename | Surname" in result.output
