"""``staff new`` must produce a tool that imports, satisfies the protocol,
passes its own generated tests and ruff, and obeys the no-pupil-data rule:
an aggregate in the output folder, nothing beside its input (#18)."""

import importlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from staffroom.core.csvio import read_csv
from staffroom.core.plugin import ToolPlugin
from staffroom.core.scaffold import class_name_for, scaffold_tool, validate_tool_name


def test_names() -> None:
    assert class_name_for("grade_boundaries") == "GradeBoundariesPlugin"
    for bad in ("Bad", "1x", "a-b", "class"):
        with pytest.raises(ValueError, match="not a valid tool name"):
            validate_tool_name(bad)


def test_scaffold_produces_working_plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Build a throwaway namespace package 'staffroom.tools' lookalike under tmp.
    pkg_root = tmp_path / "scaffolded"
    tools_dir = pkg_root / "staffroom" / "tools"
    tools_dir.mkdir(parents=True)
    written = scaffold_tool("demo_tool", tools_dir)
    assert {p.name for p in written} >= {"__init__.py", "logic.py", "panel.py", "cli.py"}

    # Import it as a real tool by extending the tools package path.
    import staffroom.tools as tools_pkg

    monkeypatch.setattr(tools_pkg, "__path__", [*tools_pkg.__path__, str(tools_dir)])
    module = importlib.import_module("staffroom.tools.demo_tool")
    plugin = module.plugin
    assert isinstance(plugin, ToolPlugin)
    assert plugin.name == "demo_tool"
    spec = plugin.panel_spec()
    assert spec.title == "Demo tool"
    assert "source" in spec.input_keys()
    # Neither optional attribute is set, so it sorts after the shipped tools and shows.
    from staffroom.core.plugin import DEFAULT_ORDER, plugin_hidden, plugin_order

    assert plugin_order(plugin) == DEFAULT_ORDER and plugin_hidden(plugin) is False
    assert "order = " in (tools_dir / "demo_tool" / "__init__.py").read_text()

    with pytest.raises(FileExistsError):
        scaffold_tool("demo_tool", tools_dir)

    # The generated logic test passes in-process too (the whole generated suite
    # runs in a copy of the checkout below).
    generated = importlib.import_module("staffroom.tools.demo_tool.tests.test_logic")
    generated.test_summarise_gives_one_row_per_question_not_per_script()


# ---------------------------------------------------------------- a contributor's first run (#18)
REPO = Path(__file__).resolve().parents[1]


def _files(folder: Path) -> dict[str, tuple[int, int]]:
    return {
        str(p.relative_to(folder)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def _ok(args: list[str], cwd: Path, env: dict[str, str]) -> str:
    done = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=90)
    assert done.returncode == 0, f"{' '.join(args)}\n{done.stdout}\n{done.stderr}"
    return done.stdout + done.stderr


@pytest.fixture
def checkout_copy(tmp_path: Path) -> Path:
    """A throwaway copy of the parts of a checkout ``just new`` and ``just check``
    see: the package, the examples, the ruff/pytest config and the conftest."""
    root = tmp_path / "checkout"
    skip = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(REPO / "src" / "staffroom", root / "src" / "staffroom", ignore=skip)
    shutil.copytree(REPO / "examples", root / "examples")
    for name in ("pyproject.toml", "conftest.py"):
        shutil.copy2(REPO / name, root / name)
    return root


def test_scaffolded_tool_is_lint_clean_tested_and_writes_only_an_aggregate_elsewhere(
    checkout_copy: Path, tmp_path: Path
) -> None:
    """``just new x && staff x run examples/marks_10x.csv`` as a contributor runs
    it: the new package passes ruff (so its first commit gets past the hook)
    and its own tests, and the run writes one per-question summary into the
    output folder, nothing into ``examples/`` and nothing per script."""
    examples = checkout_copy / "examples"
    examples_before, repo_examples_before = _files(examples), _files(REPO / "examples")
    tool = checkout_copy / "src" / "staffroom" / "tools" / "reading_age"
    scaffold_tool("reading_age", tool.parent)

    home, sessions = tmp_path / "home", tmp_path / "sessions"
    home.mkdir()
    (home / "config.toml").write_text(f'[general]\nsessions_root = "{sessions}"\n')
    env = {
        **os.environ,
        "PYTHONPATH": str(checkout_copy / "src"),  # the copy, not the installed package
        "STAFFROOM_HOME": str(home),
        "QT_QPA_PLATFORM": "offscreen",
    }
    py = sys.executable
    _ok([py, "-m", "ruff", "check", "--no-cache", str(tool)], checkout_copy, env)
    _ok([py, "-m", "ruff", "format", "--check", "--no-cache", str(tool)], checkout_copy, env)
    tests = _ok([py, "-m", "pytest", "-p", "no:cacheprovider", str(tool)], checkout_copy, env)
    assert "3 passed" in tests, tests

    cli = "import sys; from staffroom.cli import main; sys.argv[0] = 'staff'; main()"
    said = _ok([py, "-c", cli, "reading_age", "run", "examples/marks_10x.csv"], checkout_copy, env)
    assert "pupil" not in said.lower()

    assert _files(examples) == examples_before
    assert _files(REPO / "examples") == repo_examples_before
    written = [p for p in sessions.rglob("*") if p.is_file()]
    assert [p.relative_to(sessions).parts[:2] for p in written] == [("outputs", "reading_age")]
    summary = read_csv(written[0])
    marks = read_csv(examples / "marks_10x.csv")
    assert len(summary) == len(marks.columns)  # one row per question, none per script
    assert summary.columns[0] == "Question"


def test_adding_a_tool_examples_keep_the_rules() -> None:
    """The contributor guide's code models the hard rules (#18): no per-row file
    such as ``_graded.csv``, no "pupils" for rows, the current vocabulary."""
    page = (REPO / "docs" / "adding-a-tool.md").read_text(encoding="utf-8")
    code = "\n".join(re.findall(r"```(?:python|bash)\n(.*?)```", page, flags=re.DOTALL))
    assert "def run(" in code and "PanelSpec(" in code
    for banned in ("pupil", "_graded", "with_column", "LogArea", "ImageView"):
        assert banned not in code, f"docs/adding-a-tool.md example uses {banned!r}"
    assert "chip=True" in code and "output_folder" in code
