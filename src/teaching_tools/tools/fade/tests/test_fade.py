import itertools
from pathlib import Path

import pytest
from typer.testing import CliRunner

from teaching_tools.cli import app
from teaching_tools.core.config import load_config
from teaching_tools.core.plugin import RunContext
from teaching_tools.tools.fade import logic, plugin
from teaching_tools.tools.fade.logic import BLANK, Options

runner = CliRunner()
PROGRAM = """def total(items):
    result = 0
    for item in items:
        result += item
    return result

# a comment
numbers = [1, 2, 3]
print(total(numbers))
"""


def test_fade_bottom_up_is_monotonic_and_keeps_headers() -> None:
    versions = logic.fade_versions(PROGRAM, Options(steps=3))
    counts = [logic.blank_count(v) for v in versions]
    assert counts == [2, 3, 5]  # 5 fadeable lines (def/for headers kept, comment skipped)
    assert versions[0].splitlines()[-1] == BLANK and versions[0].splitlines()[-2] == BLANK
    last = versions[-1].splitlines()
    assert last[0] == "def total(items):" and last[2] == "    for item in items:"
    assert last[1] == "    " + BLANK and last[4] == "    " + BLANK
    assert "# a comment" in versions[-1]
    for earlier, later in itertools.pairwise(versions):
        blanked_earlier = {i for i, ln in enumerate(earlier.splitlines()) if ln.strip() == BLANK}
        blanked_later = {i for i, ln in enumerate(later.splitlines()) if ln.strip() == BLANK}
        assert blanked_earlier <= blanked_later


def test_top_down_ranges_and_blank_headers() -> None:
    top = logic.fade_versions(PROGRAM, Options(steps=1, order="top_down", keep_headers=False))[0]
    assert top.splitlines()[0] == BLANK  # the def line too
    ranged = logic.fade_versions(PROGRAM, Options(steps=2, order="ranges", ranges="2, 8-9"))
    assert [logic.blank_count(v) for v in ranged] == [2, 3]  # round(1.5) = 2
    assert ranged[0].splitlines()[1] == "    " + BLANK
    assert logic.parse_ranges("3-5, 8, 5") == [3, 4, 5, 8]
    with pytest.raises(ValueError, match="Nothing to fade"):
        logic.fade_versions(PROGRAM, Options(order="ranges", ranges="1"))  # line 1 is a kept header


def test_plugin_and_cli(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    result = plugin.run({"pasted": PROGRAM, "options": Options(steps=2, formats="pdf")}, ctx)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "pasted_code_faded.pdf",
        "pasted_code_faded_key.pdf",
    ]
    assert (
        "Version 2 of 2" in result.texts["preview"]
        and "Complete program" in result.texts["preview"]
    )
    src = tmp_path / "sol.py"
    src.write_text(PROGRAM)
    r = runner.invoke(
        app,
        [
            "fade",
            "make",
            str(src),
            "-k",
            "3",
            "--order",
            "top_down",
            "-f",
            "docx",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert (tmp_path / "sol_faded_key.docx").exists()
    r = runner.invoke(app, ["fade", "make", str(src), "--order", "sideways"])
    assert r.exit_code == 1
