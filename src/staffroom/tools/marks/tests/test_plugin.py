"""Acceptance: saved outputs contain no per-row data; identifier columns are
dropped with a warning; presets round-trip through config."""

from pathlib import Path

from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import load_config
from staffroom.core.csvio import read_table, write_table
from staffroom.core.panel import EditableTable
from staffroom.core.plugin import RunContext
from staffroom.core.table import Table
from staffroom.tools.marks import plugin, presets
from staffroom.tools.marks.logic import Options

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


def test_markbook_max_row_in_name_column_is_found(tmp_path: Path) -> None:
    # An .xlsx markbook export: MAX sits in the surname column, which the filter drops.
    src = write_table(
        Table(
            ["Surname", "Forename", "q1", "q2"],
            [["MAX", None, 4, 6], ["s1", "f1", 3, 5], ["s2", "f2", 4, 6], ["s3", "f3", 1, 2]],
            fake_data=True,
        ),
        tmp_path / "markbook.xlsx",
    )
    logs: list[str] = []
    ctx = RunContext(config=load_config(), output_dir=tmp_path / "out", log=logs.append)
    result = plugin.run({"marks": src, "options": Options()}, ctx)
    assert any("Dropped identifier column(s), never used: Surname, Forename" in m for m in logs)
    assert any("3 scripts, paper total 10 (q1=4, q2=6)" in m for m in logs)
    assert not any("highest mark seen" in m for m in logs)
    assert len(result.tables["grades"]) == 3
    for p in (tmp_path / "out").glob("*.csv"):
        saved = read_table(p)
        assert not {"s1", "f1", "MAX"} & {str(v) for row in saved.rows for v in row}


def test_warnings_reach_the_log_and_cli_and_nothing_per_row_is_saved(
    example_marks_messy: Path, tmp_path: Path
) -> None:
    logs: list[str] = []
    ctx = RunContext(config=load_config(), output_dir=tmp_path / "gui", log=logs.append)
    result = plugin.run({"marks": example_marks_messy, "options": Options()}, ctx)
    joined = "\n".join(logs)
    assert "Warning: q3 has a max of 0" in joined
    assert "Warning: q1: 1 script scored above the max of 4 (highest 5)" in joined
    assert "Warning: 6 blank or non-numeric cells (q1: 1, q2: 2, q3: 1, q4: 2)" in joined
    assert "3 of 5 scripts incomplete" in joined
    assert "3 warnings" in result.summary
    assert result.tables["distribution"].rows[-1][:2] == ["Incomplete scripts", 3]
    # The over-max script (row 2: 5,3,1,blank) is in no saved file.
    for p in (tmp_path / "gui").glob("*.csv"):
        text = p.read_text()
        assert "5,3,1" not in text and "ab" not in text
    r = runner.invoke(
        app, ["marks", "run", str(example_marks_messy), "--out", str(tmp_path / "cli")]
    )
    assert r.exit_code == 0, r.output
    assert "Warning: q3 has a max of 0" in r.output
    assert "Warning: q1: 1 script scored above the max of 4" in r.output
    assert "5 scripts graded; 3 warnings" in r.output
    r = runner.invoke(
        app,
        ["marks", "run", str(example_marks_messy), "--unit", "raw", "--out", str(tmp_path / "raw")],
    )
    assert r.exit_code == 0
    assert "above the paper total of 20" in r.output
