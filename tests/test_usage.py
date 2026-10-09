from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import Config
from staffroom.core.usage import record_run, summary, usage_file

runner = CliRunner()


def test_record_and_summarise(tmp_path: Path) -> None:
    path = tmp_path / "usage.toml"
    record_run("marks", path=path, when=datetime(2026, 10, 1, tzinfo=UTC))
    record_run("marks", path=path, when=datetime(2026, 10, 8, tzinfo=UTC))
    record_run("quiz", path=path, when=datetime(2026, 10, 2, tzinfo=UTC))
    rows = summary(path)
    assert [(u.name, u.runs, u.last_used) for u in rows] == [
        ("marks", 2, "2026-10-08"),
        ("quiz", 1, "2026-10-02"),
    ]
    assert "input" not in path.read_text()  # only names, counts and dates


def test_cli_usage_lists_never_run_tools(isolated_home: Path) -> None:
    r = runner.invoke(app, ["usage"])
    assert r.exit_code == 0 and "nothing recorded" in r.output
    record_run("hello")
    assert usage_file().exists()
    r = runner.invoke(app, ["usage"])
    assert "hello" in r.output and "never run:" in r.output and "marks" in r.output


# --- CLI runs are recorded too (#28) -------------------------------------------


def test_cli_run_records_usage(isolated_home: Path, example_marks: Path, tmp_path: Path) -> None:
    """A successful ``staff <tool> <command>`` counts as a run of that tool, under
    the same home the launcher records into."""
    r = runner.invoke(app, ["hello", "run", str(example_marks), "--out", str(tmp_path / "o")])
    assert r.exit_code == 0, r.output
    assert usage_file() == isolated_home / "usage.toml" and usage_file().exists()
    rows = summary()
    assert [(u.name, u.runs, u.cli_runs, u.launcher_runs) for u in rows] == [("hello", 1, 1, 0)]
    text = usage_file().read_text()
    assert "marks_10x" not in text and str(tmp_path) not in text  # never inputs or paths


def test_cli_failed_run_is_not_recorded(isolated_home: Path, tmp_path: Path) -> None:
    """A run that ends in a teacher-facing error (here: an unsupported file type)
    is not a use of the tool."""
    bad = tmp_path / "notes.txt"
    bad.write_text("# FAKE DATA\nnot a marks file\n")
    r = runner.invoke(app, ["hello", "run", str(bad)])
    assert r.exit_code == 1
    assert not usage_file().exists()


def test_cli_run_survives_an_unwritable_usage_file(
    isolated_home: Path, example_marks: Path, tmp_path: Path
) -> None:
    """When usage.toml cannot be written (here it is a folder, so the write
    raises an OSError) the run still succeeds and nothing is recorded."""
    usage_file().mkdir(parents=True)
    r = runner.invoke(app, ["hello", "run", str(example_marks), "--out", str(tmp_path / "o")])
    assert r.exit_code == 0, r.output
    assert usage_file().is_dir() and not any(usage_file().iterdir())


def test_cli_run_skips_recording_when_config_is_read_only(
    isolated_home: Path, example_marks: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``read_only`` on the config (one-off runs that must not persist anything)
    turns usage recording off as well."""
    import staffroom.cli as cli

    monkeypatch.setattr(cli, "load_config", lambda: Config(read_only=True))
    r = runner.invoke(app, ["hello", "run", str(example_marks), "--out", str(tmp_path / "o")])
    assert r.exit_code == 0, r.output
    assert not usage_file().exists()


def test_launcher_and_cli_counts_are_kept_apart(tmp_path: Path) -> None:
    """``runs`` stays the total (older files only have that); ``cli_runs`` is the
    CLI's share, so launcher use is what is left."""
    path = tmp_path / "usage.toml"
    # An entry written before CLI runs were counted: total only.
    path.write_text('[tools.marks]\nruns = 3\nlast_used = "2026-09-30"\n')
    assert record_run("marks", path=path, when=datetime(2026, 10, 1, tzinfo=UTC), source="cli")
    assert record_run("marks", path=path, when=datetime(2026, 10, 2, tzinfo=UTC))
    (u,) = summary(path)
    assert (u.runs, u.cli_runs, u.launcher_runs, u.last_used) == (5, 1, 4, "2026-10-02")


def test_record_run_returns_false_instead_of_raising_when_unwritable(tmp_path: Path) -> None:
    blocked = tmp_path / "file-not-dir"
    blocked.write_text("")
    assert record_run("hello", path=blocked / "usage.toml") is False


def test_cli_usage_shows_launcher_and_cli_shares(isolated_home: Path) -> None:
    record_run("marks")
    record_run("marks", source="cli")
    record_run("marks", source="cli")
    r = runner.invoke(app, ["usage"])
    assert r.exit_code == 0, r.output
    line = next(line for line in r.output.splitlines() if line.startswith("marks"))
    assert "3 run(s)" in line and "launcher 1" in line and "cli 2" in line
