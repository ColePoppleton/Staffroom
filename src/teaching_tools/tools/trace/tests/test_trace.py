"""Acceptance: the trace of a known 10-line loop matches a hand-written table."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from teaching_tools.cli import app
from teaching_tools.core.config import load_config
from teaching_tools.core.plugin import RunContext, ToolError
from teaching_tools.tools.trace import logic, plugin, run_trace
from teaching_tools.tools.trace.logic import Options

runner = CliRunner()

TEN_LINES = """total = 0
count = 1
limit = 3
while count <= limit:
    total = total + count
    count = count + 1
    print(count)
print("done")
average = total / limit
print(average)
"""

# Hand-written: (line, total, count, limit, average, output) after each executed line.
EXPECTED = [
    (1, "0", "", "", "", ""),
    (2, "0", "1", "", "", ""),
    (3, "0", "1", "3", "", ""),
    (4, "0", "1", "3", "", ""),
    (5, "1", "1", "3", "", ""),
    (6, "1", "2", "3", "", ""),
    (7, "1", "2", "3", "", "2"),
    (4, "1", "2", "3", "", ""),
    (5, "3", "2", "3", "", ""),
    (6, "3", "3", "3", "", ""),
    (7, "3", "3", "3", "", "3"),
    (4, "3", "3", "3", "", ""),
    (5, "6", "3", "3", "", ""),
    (6, "6", "4", "3", "", ""),
    (7, "6", "4", "3", "", "4"),
    (4, "6", "4", "3", "", ""),
    (8, "6", "4", "3", "", "done"),
    (9, "6", "4", "3", "2.0", ""),
    (10, "6", "4", "3", "2.0", "2.0"),
]


def test_ten_line_loop_matches_hand_written_table() -> None:
    result = run_trace(TEN_LINES, "", 100)
    assert result.error is None and not result.truncated
    assert result.variables == ["total", "count", "limit", "average"]
    table = logic.trace_table(
        logic.select_steps(result, TEN_LINES, logic.Options().kinds()), result.variables
    )
    assert table.columns == ["Line", "total", "count", "limit", "average", "Output"]
    assert [tuple(row) for row in table.rows] == EXPECTED
    assert result.stdout == "2\n3\n4\ndone\n2.0\n"


def test_kind_filter_and_blank_table() -> None:
    result = run_trace(TEN_LINES, "", 100)
    only_assign = logic.select_steps(result, TEN_LINES, {"assign"})
    assert [s.line for s in only_assign] == [1, 2, 3, 5, 6, 5, 6, 5, 6, 9]
    blank = logic.trace_table(only_assign, ["total", "count"], blank=True)
    assert blank.columns == ["Line", "total", "count", "Output"]
    assert blank.rows[0] == [1, None, None, None]
    hidden = logic.trace_table(only_assign, ["total"], blank=True, line_numbers=False)
    assert hidden.rows[0] == [None, None, None]


def test_functions_get_a_scope_column_and_inputs_work() -> None:
    source = (
        "def double(n):\n    result = n * 2\n    return result\n\n"
        "x = int(input())\nprint(double(x))\n"
    )
    result = run_trace(source, "21\n", 50)
    steps = logic.select_steps(result, source, logic.Options().kinds())
    scopes = [(s.line, s.scope) for s in steps]
    assert (2, "double") in scopes and (3, "double") in scopes
    table = logic.trace_table(steps, result.variables)
    assert "Scope" in table.columns
    assert result.stdout == "42\n"


def test_errors_are_reported_not_fatal() -> None:
    result = run_trace("x = 1\ny = x / 0\nprint(y)\n", "", 50)
    assert result.error and "ZeroDivisionError" in result.error
    assert [s.line for s in result.steps] == [1, 2]
    with pytest.raises(ToolError, match="did not finish"):
        run_trace("while True:\n    pass\n", "", 10_000, timeout=1.0)
    with pytest.raises(ToolError, match="imports socket"):
        run_trace("import socket\n", "", 10)


def test_step_cap() -> None:
    result = run_trace("i = 0\nwhile i < 1000:\n    i += 1\n", "", 25)
    assert result.truncated and len(result.steps) == 25


def test_plugin_and_cli(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    result = plugin.run({"pasted": TEN_LINES, "options": Options(formats="pdf")}, ctx)
    assert result.tables["table"].rows[-1][0] == 10
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "pasted_code_trace.pdf",
        "pasted_code_trace_key.pdf",
    ]
    src = tmp_path / "loop.py"
    src.write_text(TEN_LINES)
    r = runner.invoke(
        app,
        ["trace", "make", str(src), "--vars", "total,count", "-f", "docx", "--out", str(tmp_path)],
    )
    assert r.exit_code == 0, r.output
    assert "Line  total  count  Output" in r.output and (tmp_path / "loop_trace_key.docx").exists()
