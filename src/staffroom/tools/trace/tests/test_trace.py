"""Acceptance: the trace of a known 10-line loop matches a hand-written table."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import load_config
from staffroom.core.export import to_text
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.trace import MissingInputError, logic, plugin, run_trace
from staffroom.tools.trace.logic import Options
from staffroom.tools.trace.sheet import build_document

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


def test_print_flood_output_is_capped_inside_the_run() -> None:
    # Prints 2 MB in one go: the tracer keeps 1 MB and the key says so.
    result = run_trace("print('x' * 2_000_000)\n", "", 10)
    assert result.stdout.endswith("[output truncated at 1024 KB]\n")
    assert len(result.stdout) < 1024 * 1024 + 64
    doc = build_document(
        "flood",
        "print('x')",
        logic.trace_table([], []),
        logic.trace_table([], []),
        result.stdout,
        truncated=False,
        error=None,
    )
    assert "[output truncated at 1024 KB]" in to_text(doc.key())


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


ASKS_TWICE = (
    'width = int(input("Width? "))\nheight = int(input("Height? "))\nprint(width * height)\n'
)


def test_input_with_nothing_to_read_is_recorded_by_the_tracer() -> None:
    # The tracer wraps input(): the uncaught EOFError it raised is reported as
    # such, with how many inputs had been read, not guessed from stderr.
    result = run_trace(ASKS_TWICE, "", 50)
    assert result.input_eof and result.inputs_read == 0
    assert result.error and result.error.startswith("EOFError")
    partial = run_trace(ASKS_TWICE, "4\n", 50)
    assert partial.input_eof and partial.inputs_read == 1
    # A program that handles the EOF itself has not hit the problem.
    handled = run_trace(
        'try:\n    x = input()\nexcept EOFError:\n    x = "none"\nprint(x)\n', "", 50
    )
    assert not handled.input_eof and handled.error is None and handled.stdout == "none\n"
    # ...and an EOFError the program raises itself is an ordinary error.
    own = run_trace("raise EOFError('mine')\n", "", 50)
    assert not own.input_eof and own.error == "EOFError: mine"


def test_empty_inputs_box_is_a_tool_error_and_writes_nothing(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    ctx = RunContext(config=load_config(), output_dir=out)
    with pytest.raises(
        MissingInputError, match=r"^The pasted code asked for input, but none was given\.$"
    ):
        plugin.run({"pasted": ASKS_TWICE, "options": Options()}, ctx)
    src = tmp_path / "area.py"
    src.write_text(ASKS_TWICE)
    with pytest.raises(
        ToolError, match=r"^area\.py asked for a 2nd input, but was given only 1 line\.$"
    ):
        plugin.run({"source": src, "stdin": "4", "options": Options()}, ctx)
    r = runner.invoke(app, ["trace", "make", str(src), "--out", str(out)])
    assert r.exit_code == 1, r.output
    assert "area.py asked for input, but none was given." in r.output
    # The CLI's next step names its own way in: --stdin, not the Inputs box (#21).
    assert "Give it 2 lines with --stdin, one per input() call" in r.output
    assert "Inputs box" not in r.output
    assert list(out.iterdir()) == [], "nothing may be written for a run that got no input"


def test_missing_input_says_what_to_do_in_the_launcher(tmp_path: Path) -> None:
    """The error carries the launcher's next step and points at the Inputs box (#21)."""
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    with pytest.raises(MissingInputError) as caught:
        plugin.run({"pasted": ASKS_TWICE, "stdin": "4", "options": Options()}, ctx)
    error = caught.value
    assert error.input_key == "stdin"
    assert error.needed == "2 lines"
    assert error.input_hint == "Needs 2 lines, one per input() call."
    assert error.next_step == (
        "The pasted code calls input() twice. "
        "Type 2 lines in the Inputs box, then press Trace again."
    )
    # A call in a loop can repeat: the count is a floor, and says why.
    loop = "for i in range(3):\n    x = input()\n"
    with pytest.raises(MissingInputError) as caught:
        plugin.run({"pasted": loop, "stdin": "a\nb", "options": Options()}, ctx)
    assert caught.value.needed == "at least 3 lines"
    assert caught.value.next_step.startswith(
        "The pasted code calls input() at least once (one is in a loop). Type at least 3 lines"
    )


def test_missing_input_wording() -> None:
    from staffroom.core.codeinput import InputCalls

    assert logic.lines_needed(InputCalls(1), 0) == "1 line"
    assert logic.lines_needed(InputCalls(3), 1) == "3 lines"
    assert logic.lines_needed(InputCalls(1, "loop"), 0) == "at least 1 line"
    # The run asked for more than the code shows (input() via a name the
    # count cannot see): the run's own number is the floor.
    assert logic.lines_needed(InputCalls(1), 2) == "at least 3 lines"
    assert logic.lines_needed(None, 0) == "at least 1 line"
    assert logic.stdin_option_step("1 line") == (
        "Give it 1 line with --stdin, one per input() call; separate lines with \\n, "
        'as in --stdin "12\\n7".'
    )
    assert logic.missing_input_step("area", None, "at least 1 line") == (
        "Type at least 1 line in the Inputs box, then press Trace again."
    )


def test_other_runtime_errors_still_make_the_sheet_and_say_so(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    result = plugin.run(
        {"pasted": "x = 1\ny = x / 0\nprint(y)\n", "options": Options(formats="pdf")}, ctx
    )
    assert "ended with ZeroDivisionError: division by zero" in result.summary
    assert "ends with an error: ZeroDivisionError" in result.texts["preview"]
    assert len(result.files) == 2 and all(f.exists() for f in result.files)


# A Year 9 style program with one function: the full trace shows the call's own
# steps with a Scope column and the locals w, h and result; the Year 9 preset
# keeps only the top-level lines and variables.
AREA = (
    "def area(w, h):\n    result = w * h\n    return result\n\n"
    "width = 4\nheight = 3\nspace = area(width, height)\nprint(space)\n"
)
AREA_FULL = [
    (5, "", "4", "", "", "", "", "", ""),
    (6, "", "4", "3", "", "", "", "", ""),
    (7, "", "4", "3", "", "", "", "12", ""),
    (2, "area", "", "", "4", "3", "12", "", ""),
    (3, "area", "", "", "4", "3", "12", "", ""),
    (8, "", "4", "3", "", "", "", "12", "12"),
]
AREA_YEAR9 = [
    (5, "4", "", "", ""),
    (6, "4", "3", "", ""),
    (7, "4", "3", "12", ""),
    (8, "4", "3", "12", "12"),
]


def test_year9_function_program_matches_hand_written_tables_in_both_settings() -> None:
    result = run_trace(AREA, "", 100)
    assert result.error is None and not result.truncated
    full = Options()
    steps = logic.select_steps(result, AREA, full.kinds(), top_level_only=full.top_level_only)
    table = logic.trace_table(steps, logic.chosen_variables(result, full.variables))
    assert table.columns == [
        "Line", "Scope", "width", "height", "w", "h", "result", "space", "Output"
    ]  # fmt: skip
    assert [tuple(row) for row in table.rows] == AREA_FULL

    year9 = Options(top_level_only=True)
    steps = logic.select_steps(result, AREA, year9.kinds(), top_level_only=year9.top_level_only)
    table = logic.trace_table(steps, logic.chosen_variables(result, year9.variables, steps))
    assert table.columns == ["Line", "width", "height", "space", "Output"], "no Scope, no locals"
    assert [tuple(row) for row in table.rows] == AREA_YEAR9
    # Asking for a local by name still gets that column, so --vars keeps working.
    assert logic.chosen_variables(result, "space, result", steps) == ["space"]


def test_year9_example_without_functions_is_the_same_in_both_settings() -> None:
    source = (Path(__file__).parents[4].parent / "examples" / "year9.py").read_text()
    result = run_trace(source, "", 100)
    kinds = Options().kinds()
    full = logic.trace_table(
        logic.select_steps(result, source, kinds), logic.chosen_variables(result, "")
    )
    steps = logic.select_steps(result, source, kinds, top_level_only=True)
    year9 = logic.trace_table(steps, logic.chosen_variables(result, "", steps))
    assert "Scope" not in full.columns and full.columns == year9.columns and full.rows == year9.rows
    assert full.columns == ["Line", "scores", "total", "count", "score", "average", "Output"]


def test_preset_is_named_from_the_values_and_printed_on_the_sheet() -> None:
    assert logic.preset_name(Options()) == "Full trace"
    assert logic.preset_name(Options(top_level_only=True)) == "Year 9"
    # Steps and output format are the teacher's business; the table shape is not.
    tweaked = Options(top_level_only=True, max_steps=200, formats="pdf")
    assert logic.preset_name(tweaked) == "Year 9"
    assert logic.preset_name(Options(top_level_only=True, calls=False)) == "Custom"
    assert logic.preset_name(Options(variables="total")) == "Custom"
    table = logic.trace_table([], [])
    doc = build_document(
        "area", AREA, table, table, "", truncated=False, error=None, preset="Year 9"
    )
    assert doc.subtitle == "Year 9 · 0 steps"
    assert "Year 9" in to_text(doc.sheet()).splitlines()[2], "the header meta line"
    plain = build_document("area", AREA, table, table, "", truncated=True, error=None)
    assert plain.subtitle == "0 steps (capped)"


def test_top_level_only_through_the_plugin_and_cli(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    logged: list[str] = []
    ctx.log = logged.append
    result = plugin.run(
        {"pasted": AREA, "options": Options(top_level_only=True, formats="pdf")}, ctx
    )
    assert result.tables["table"].columns == ["Line", "width", "height", "space", "Output"]
    assert "Year 9" in result.texts["preview"].splitlines()[2]
    assert logged[0].startswith(
        "Year 9: 7 steps executed, 4 recorded; variables: width, height, space"
    )
    src = tmp_path / "area.py"
    src.write_text(AREA)
    r = runner.invoke(
        app, ["trace", "make", str(src), "--top-level-only", "-f", "docx", "--out", str(tmp_path)]
    )
    assert r.exit_code == 0, r.output
    assert "Line  width  height  space  Output" in r.output and "Scope" not in r.output
    r = runner.invoke(app, ["trace", "make", str(src), "-f", "docx", "--out", str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert "Scope" in r.output and "Full trace" in r.output
