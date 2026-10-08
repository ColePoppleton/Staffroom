from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from staffroom.cli import app
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
