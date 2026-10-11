from pathlib import Path

from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.csvio import read_csv

runner = CliRunner()


def test_hello_run_writes_a_per_question_summary(tmp_path: Path, example_marks: Path) -> None:
    result = runner.invoke(app, ["hello", "run", str(example_marks), "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "pupil" not in result.output.lower()
    out = tmp_path / "marks_10x_summary.csv"
    table = read_csv(out)
    assert table.columns == ["Question", "Answered", "Mean", "Highest"]
    assert len(table) == len(read_csv(example_marks).columns)  # one row per question
    assert table.fake_data is True


def test_hello_run_with_no_out_writes_to_the_sessions_outputs_not_examples(
    tmp_path: Path, example_marks: Path
) -> None:
    """``staff hello run examples/marks_10x.csv`` as the justfile shows it: the
    summary goes to <sessions root>/outputs/hello (a temp folder in tests),
    and ``examples/`` is left exactly as it was."""
    examples = example_marks.parent
    before = sorted(p.name for p in examples.iterdir())
    result = runner.invoke(app, ["hello", "run", str(example_marks)])
    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in examples.iterdir()) == before
    written = tmp_path / "sessions" / "outputs" / "hello" / "marks_10x_summary.csv"
    assert written.is_file()
    assert str(written) in result.output


def test_hello_run_drops_identifiers(tmp_path: Path) -> None:
    src = tmp_path / "scripts.csv"
    src.write_text("Candidate Number,q1,q2\n1001,3,4\n")
    result = runner.invoke(app, ["hello", "run", str(src), "--out", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert "Dropped identifier column(s): Candidate Number" in result.output
    out = read_csv(tmp_path / "out" / "scripts_summary.csv")
    assert out.column("Question") == ["q1", "q2"]
    assert "1001" not in (tmp_path / "out" / "scripts_summary.csv").read_text()
    assert not (tmp_path / "scripts_summary.csv").exists()  # nothing beside the input


def test_hello_preview(example_marks: Path) -> None:
    result = runner.invoke(app, ["hello", "preview", str(example_marks), "--rows", "2"])
    assert result.exit_code == 0, result.output
    assert "q1 | q2" in result.output
