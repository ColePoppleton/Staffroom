import itertools
from pathlib import Path

import pytest
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.fade import logic, plugin
from staffroom.tools.fade.logic import BLANK, Options

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


def test_versions_are_capped_at_the_fadeable_line_count(tmp_path: Path) -> None:
    two_lines = "x = 1\nprint(x)\n"
    versions = logic.fade_versions(two_lines, Options(steps=8))
    assert [logic.blank_count(v) for v in versions] == [1, 2]
    # Whatever the sizes, every version has a blank and strictly more than the one before.
    for n in range(1, 13):
        program = "\n".join(f"v{i} = {i}" for i in range(n)) + "\n"
        for steps in range(1, 13):
            counts = [
                logic.blank_count(v) for v in logic.fade_versions(program, Options(steps=steps))
            ]
            assert len(counts) == min(steps, n), (n, steps)
            assert counts[0] >= 1 and counts[-1] == n, (n, steps)
            assert all(a < b for a, b in itertools.pairwise(counts)), (n, steps, counts)
    logged: list[str] = []
    ctx = RunContext(config=load_config(), output_dir=tmp_path, log=logged.append)
    result = plugin.run({"pasted": two_lines, "options": Options(steps=8, formats="pdf")}, ctx)
    assert result.texts["preview"].count("Version ") == 2
    assert any("8 versions" in m and "2" in m for m in logged), logged


def test_invalid_python_is_refused_with_the_shared_message(tmp_path: Path) -> None:
    broken = "def oops(\n    x = 1\n"
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    with pytest.raises(ToolError, match=r"not valid Python: .* \(line [12]\)"):
        plugin.run({"pasted": broken, "options": Options()}, ctx)
    assert list(tmp_path.iterdir()) == []
    src = tmp_path / "broken.py"
    src.write_text(broken)
    r = runner.invoke(app, ["fade", "make", str(src), "--out", str(tmp_path)])
    assert r.exit_code == 1 and "not valid Python" in r.output


def test_range_errors_say_what_was_expected_and_what_is_wrong() -> None:
    with pytest.raises(ValueError, match="Line ranges like 3-5, 8"):
        logic.fade_versions(PROGRAM, Options(order="ranges", ranges="abc"))
    with pytest.raises(ValueError, match="no lines are listed"):
        logic.fade_versions(PROGRAM, Options(order="ranges", ranges="  "))
    with pytest.raises(ValueError, match=r"Lines 10-12 are past the end .*9 lines"):
        logic.fade_versions(PROGRAM, Options(order="ranges", ranges="8-12"))
    with pytest.raises(ValueError, match=r"Line 0 .*start at 1"):
        logic.fade_versions(PROGRAM, Options(order="ranges", ranges="0, 2"))
    with pytest.raises(ValueError) as excinfo:
        logic.fade_versions(PROGRAM, Options(order="ranges", ranges="1, 6-7"))
    message = str(excinfo.value)
    assert "Nothing to fade" in message
    assert "line 1 is a def/if/for/while header" in message and "Keep headers" in message
    assert "line 6 is blank" in message and "line 7 is a comment" in message
    # Listing ranges without choosing the ranges order is almost certainly a slip.
    with pytest.raises(ValueError, match="Fade order is 'bottom_up'"):
        logic.fade_versions(PROGRAM, Options(order="bottom_up", ranges="3-5"))
    # Lines that cannot fade are reported but do not stop the others fading.
    assert logic.unfadeable_lines(PROGRAM, Options(order="ranges", ranges="1-2, 8")) == [
        (1, "line 1 is a def/if/for/while header (Keep headers is on)")
    ]
    versions = logic.fade_versions(PROGRAM, Options(steps=2, order="ranges", ranges="1-2, 8"))
    assert [logic.blank_count(v) for v in versions] == [1, 2]
    with pytest.raises(ValueError, match="every line is a header, a comment or blank"):
        logic.fade_versions("# only a comment\n", Options())
