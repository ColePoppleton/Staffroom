"""Acceptance: saved outputs contain no per-row data; identifier columns are
dropped with a warning; presets round-trip through config."""

from pathlib import Path

from typer.testing import CliRunner

from teaching_tools.cli import app
from teaching_tools.core.config import load_config
from teaching_tools.core.csvio import read_table
from teaching_tools.core.panel import EditableTable
from teaching_tools.core.plugin import RunContext
from teaching_tools.core.table import Table
from teaching_tools.tools.marks import plugin, presets
from teaching_tools.tools.marks.logic import Options

runner = CliRunner()


def test_run_saves_aggregates_only(example_marks_max: Path, tmp_path: Path) -> None:
    logs: list[str] = []
    ctx = RunContext(config=load_config(), output_dir=tmp_path, log=logs.append)
    result = plugin.run({"marks": example_marks_max, "options": Options()}, ctx)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [
        "marks_10x_max_distribution.csv",
        "marks_10x_max_distribution.png",
        "marks_10x_max_questions.csv",
    ]
    dist = read_table(tmp_path / "marks_10x_max_distribution.csv")
    assert dist.columns == ["Grade", "Count", "Percent"] and dist.fake_data
    questions = read_table(tmp_path / "marks_10x_max_questions.csv")
    assert questions.columns[0] == "Question" and len(questions) == 6
    # Nothing per script on disk: no saved file carries question or total columns.
    for p in tmp_path.glob("*.csv"):
        saved = read_table(p)
        assert "Total" not in saved.columns and "Grade" not in saved.columns[1:]
        assert not any(c.lower().startswith("q") and c != "Question" for c in saved.columns)
    assert (tmp_path / "marks_10x_max_distribution.png").stat().st_size > 1000
    assert result.tables["grades"].columns[-1] == "Grade"  # view only
    assert "paper total 40" in " ".join(logs)


def test_identifier_column_dropped_with_warning(tmp_path: Path) -> None:
    src = tmp_path / "with_names.csv"
    src.write_text("Name,q1,q2\nMAX,4,6\nx,3,5\ny,4,6\nz,1,2\n")
    logs: list[str] = []
    ctx = RunContext(config=load_config(), output_dir=tmp_path / "out", log=logs.append)
    result = plugin.run({"marks": src, "options": Options()}, ctx)
    assert any("Dropped identifier column(s), never used: Name" in m for m in logs)
    assert "Name" not in result.tables["grades"].columns
    for p in (tmp_path / "out").glob("*.csv"):
        saved = read_table(p)
        assert "Name" not in saved.columns
        assert "x" not in {str(v) for row in saved.rows for v in row}


def test_preset_round_trips_through_config(tmp_path: Path) -> None:
    config = load_config()
    ctx = RunContext(config=config, output_dir=tmp_path)
    custom = Table(["Grade", "Minimum"], [["Pass", 50.0], ["Fail", 0.0]])
    result = plugin.act("save_preset", {"name": "Mock Nov", "table": custom}, ctx)
    assert "Mock Nov" in result.summary
    again = presets.all_presets(load_config())
    assert again["Mock Nov"] == (("Pass", 50.0), ("Fail", 0.0))
    assert presets.DEFAULT_PRESET in again
    spec = plugin.panel_spec()
    grid = next(w for w in spec.inputs if isinstance(w, EditableTable))
    assert "Mock Nov" in dict(grid.presets)


def test_cli_run_and_presets(example_marks_max: Path, tmp_path: Path) -> None:
    r = runner.invoke(app, ["marks", "run", str(example_marks_max), "--out", str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert "Grade distribution" in r.output and "q6" in r.output
    assert "10 scripts graded" in r.output
    assert (tmp_path / "marks_10x_max_distribution.png").exists()
    r = runner.invoke(app, ["marks", "run", str(example_marks_max), "--preset", "nope"])
    assert r.exit_code == 1 and "unknown preset" in r.output
    r = runner.invoke(app, ["marks", "presets"])
    assert r.exit_code == 0 and "OCR J277" in r.output and "A-level" in r.output
    r = runner.invoke(
        app, ["marks", "run", str(example_marks_max), "--unit", "raw", "--out", str(tmp_path)]
    )
    assert r.exit_code == 0, (
        r.output
    )  # raw boundaries from a percent preset: everything scores high
