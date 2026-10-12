"""hello keeps the rules the scaffold keeps (#18): an aggregate, in the
output folder, never beside its input; and it stays what ``staff new``
generates, so the reference and the scaffold cannot drift apart."""

import importlib
from pathlib import Path

import pytest

from staffroom.core.config import Config
from staffroom.core.csvio import read_csv, read_table, write_table
from staffroom.core.plugin import RunContext
from staffroom.core.scaffold import scaffold_tool
from staffroom.core.table import Table
from staffroom.tools.hello import logic, plugin


def test_run_saves_a_summary_in_the_output_folder(tmp_path: Path) -> None:
    marks = Table(["q1", "q2"], [[3, 4], [1, 2], [2, 0]], fake_data=True)
    source = write_table(marks, tmp_path / "class" / "marks.csv")
    config = Config(path=tmp_path / "config.toml")
    config.general.output_dir = str(tmp_path / "out")
    # The shell's ctx.output_dir is the input's folder when nothing is set.
    ctx = RunContext(config=config, output_dir=source.parent)

    result = plugin.run({"source": source, "options": logic.Options()}, ctx)

    assert [p.parent for p in result.files] == [tmp_path / "out"]
    assert sorted(p.name for p in source.parent.iterdir()) == ["marks.csv"]
    assert len(read_csv(result.files[0])) == 2  # one row per question, none per script
    assert "pupil" not in result.summary.lower() and "pupil" not in result.outcome.lower()


def test_with_nothing_configured_it_writes_under_the_sessions_root(
    tmp_path: Path, example_marks: Path
) -> None:
    config = Config(path=tmp_path / "config.toml")
    ctx = RunContext(config=config, output_dir=example_marks.parent)
    result = plugin.run({"source": example_marks}, ctx)
    assert result.files == [tmp_path / "sessions" / "outputs" / "hello" / "marks_10x_summary.csv"]
    assert plugin.panel_spec().writes_to is not None


def test_hello_summarises_exactly_as_a_fresh_scaffold_does(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, example_marks: Path
) -> None:
    tools_dir = tmp_path / "staffroom" / "tools"
    tools_dir.mkdir(parents=True)
    scaffold_tool("hello_twin", tools_dir)
    import staffroom.tools as tools_pkg

    monkeypatch.setattr(tools_pkg, "__path__", [*tools_pkg.__path__, str(tools_dir)])
    twin = importlib.import_module("staffroom.tools.hello_twin.logic")
    table = read_table(example_marks)
    ours, theirs = logic.summarise(table), twin.summarise(table, twin.Options())
    assert (ours.columns, ours.rows) == (theirs.columns, theirs.rows)
