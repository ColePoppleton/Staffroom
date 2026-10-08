from pathlib import Path

from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.csvio import read_csv

runner = CliRunner()


def test_hello_run_writes_output(tmp_path: Path, example_marks: Path) -> None:
    result = runner.invoke(app, ["hello", "run", str(example_marks), "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    out = tmp_path / "marks_10x_totals.csv"
    assert out.exists()
    table = read_csv(out)
    assert table.columns[-1] == "Total"
    assert table.column("Total")[0] == 37
    assert table.fake_data is True


def test_hello_run_drops_identifiers(tmp_path: Path) -> None:
    src = tmp_path / "scripts.csv"
    src.write_text("Candidate Number,q1,q2\n1001,3,4\n")
    result = runner.invoke(app, ["hello", "run", str(src), "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Dropped identifier column(s): Candidate Number" in result.output
    out = read_csv(tmp_path / "scripts_totals.csv")
    assert out.columns == ["q1", "q2", "Total"]


def test_hello_preview(example_marks: Path) -> None:
    result = runner.invoke(app, ["hello", "preview", str(example_marks), "--rows", "2"])
    assert result.exit_code == 0, result.output
    assert "q1 | q2" in result.output
