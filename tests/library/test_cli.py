from pathlib import Path

import pytest
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import load_config

runner = CliRunner()


@pytest.fixture(autouse=True)
def _configure_root(resources_root: Path) -> None:
    cfg = load_config()
    cfg.general.resources_root = str(resources_root)
    cfg.save()


def test_index_search_tags_status() -> None:
    r = runner.invoke(app, ["library", "search", "while"])
    assert r.exit_code == 1 and "index is empty" in r.output

    r = runner.invoke(app, ["library", "index"])
    assert r.exit_code == 0, r.output
    assert "files scanned" in r.output

    r = runner.invoke(app, ["library", "search", "while", "--kind", "python"])
    assert r.exit_code == 0, r.output
    assert "while_loops.py" in r.output and "booklet.pdf" not in r.output

    r = runner.invoke(
        app, ["library", "tags", "Python/notes.md", "--set", "loops,ks3", "--notes", "hi"]
    )
    assert r.exit_code == 0, r.output
    assert "tags:  loops, ks3" in r.output

    r = runner.invoke(app, ["library", "search", "loops", "--tag", "ks3"])
    assert "notes.md" in r.output

    r = runner.invoke(app, ["library", "status"])
    assert r.exit_code == 0 and "files:" in r.output


def test_index_missing_root(tmp_path: Path) -> None:
    cfg = load_config()
    cfg.general.resources_root = str(tmp_path / "missing")
    cfg.save()
    r = runner.invoke(app, ["library", "index"])
    assert r.exit_code == 1 and "not found" in r.output


def test_exclude_command_and_name_only_report(resources_root: Path) -> None:
    (resources_root / "Python" / "task_submission.py").write_text(
        "# Candidate number: 4021\nprint(1)\n"
    )
    r = runner.invoke(app, ["library", "index"])
    assert r.exit_code == 0, r.output
    assert "1 file skipped for text" in r.output
    assert "name only: Python/task_submission.py" in r.output

    r = runner.invoke(app, ["library", "status"])
    assert r.exit_code == 0, r.output
    assert "name only:   1 file" in r.output
    assert "excluded:    -" in r.output
    assert "only read" in r.output

    r = runner.invoke(app, ["library", "exclude", "--add", "OCR Booklet", "--add", "*.csv"])
    assert r.exit_code == 0, r.output
    assert "configured:  OCR Booklet, *.csv" in r.output
    assert load_config().general.library_exclude == ["OCR Booklet", "*.csv"]

    r = runner.invoke(app, ["library", "index"])
    assert r.exit_code == 0, r.output
    assert "4 removed" in r.output and "2 exclusion pattern(s)" in r.output
    r = runner.invoke(app, ["library", "search", "while"])
    assert "exercise_3a.py" not in r.output and "while_loops.py" in r.output

    r = runner.invoke(app, ["library", "exclude", "--remove", "*.csv", "--remove", "nope"])
    assert r.exit_code == 0, r.output
    assert "not in the list: nope" in r.output
    assert load_config().general.library_exclude == ["OCR Booklet"]
    r = runner.invoke(app, ["library", "exclude"])
    assert "configured:  OCR Booklet" in r.output and "ignore file: -" in r.output
