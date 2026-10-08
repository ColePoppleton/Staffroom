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
