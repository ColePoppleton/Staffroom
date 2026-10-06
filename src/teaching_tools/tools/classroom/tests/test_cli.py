from pathlib import Path

import pytest
from typer.testing import CliRunner

from teaching_tools.cli import app
from teaching_tools.core import launch
from teaching_tools.core.config import load_config

runner = CliRunner()


@pytest.fixture(autouse=True)
def _setup(
    resources_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> list[list[str]]:
    cfg = load_config()
    cfg.general.resources_root = str(resources_root)
    cfg.general.sessions_root = str(tmp_path / "sessions")
    cfg.save()
    runs: list[list[str]] = []
    monkeypatch.setattr(launch, "_popen", lambda argv: runs.append(list(argv)))
    return runs


def test_open_list_diff_promote_reopen(resources_root: Path, tmp_path: Path) -> None:
    original = resources_root / "Python" / "Python_Course" / "while_loops.py"
    r = runner.invoke(app, ["classroom", "open", str(original), "--label", "P3 Y9 loops"])
    assert r.exit_code == 0, r.output
    assert "Copied while_loops.py" in r.output
    copy = Path(r.output.strip().splitlines()[-1])
    assert copy.exists() and copy.parent.name == "P3 Y9 loops"
    copy.write_text("# edited\n" + copy.read_text())

    r = runner.invoke(app, ["classroom", "list"])
    assert r.exit_code == 0 and "while_loops.py" in r.output and "P3 Y9 loops" in r.output

    rel = copy.relative_to(tmp_path / "sessions").as_posix()
    r = runner.invoke(app, ["classroom", "diff", rel])
    assert r.exit_code == 0 and "+# edited" in r.output

    r = runner.invoke(app, ["classroom", "promote", rel])
    assert r.exit_code == 0 and "while_loops_v2.py" in r.output
    assert (original.parent / "while_loops_v2.py").exists()

    r = runner.invoke(app, ["classroom", "reopen", rel])
    assert r.exit_code == 0 and "Re-opened" in r.output

    r = runner.invoke(app, ["classroom", "diff", "2026-01-01/nope/x.py"])
    assert r.exit_code == 1 and "No such session file" in r.output


def test_open_rejects_bad_label(resources_root: Path) -> None:
    original = resources_root / "Python" / "notes.md"
    r = runner.invoke(app, ["classroom", "open", str(original), "--label", "   "])
    assert r.exit_code == 1 and "short label" in r.output
