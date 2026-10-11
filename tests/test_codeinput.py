"""core.codeinput: the one place a code tool's input becomes source text, and
the CodeSource vocabulary it reads (#86)."""

from __future__ import annotations

from pathlib import Path

import pytest

from staffroom.core.codeinput import (
    INPUTS_PLACEHOLDER,
    InputCalls,
    code_from_inputs,
    code_path,
    count_input_calls,
    input_calls_phrase,
    inputs_placeholder,
    inspect_inputs_box,
)
from staffroom.core.panel import (
    Choice,
    CodeSource,
    CodeValue,
    PanelSpec,
    ResultsTable,
    TextArea,
)
from staffroom.core.plugin import ToolError


def test_the_file_wins_and_is_read_afresh(tmp_path: Path) -> None:
    program = tmp_path / "loop.py"
    program.write_text("print(2)\n", encoding="utf-8")
    # The view showed an older text; the run reads what is on disk now.
    inputs = {"source": CodeValue(program, "print(1)")}
    assert code_from_inputs(inputs) == ("print(2)\n", "loop")
    assert code_path(inputs) == program


def test_pasted_text_when_no_file() -> None:
    assert code_from_inputs({"source": CodeValue(None, "x = 1\n")}) == ("x = 1\n", "pasted_code")
    assert code_path({"source": CodeValue(None, "x = 1\n")}) is None


def test_command_line_inputs_still_work(tmp_path: Path) -> None:
    program = tmp_path / "loop.py"
    program.write_text("print(3)\n", encoding="utf-8")
    assert code_from_inputs({"source": program}) == ("print(3)\n", "loop")
    assert code_from_inputs({"pasted": "y = 2\n"}) == ("y = 2\n", "pasted_code")


@pytest.mark.parametrize(
    "inputs", [{}, {"source": CodeValue(None, "  \n")}, {"source": None, "pasted": ""}]
)
def test_nothing_is_one_line_for_the_teacher(inputs: dict[str, object]) -> None:
    with pytest.raises(ToolError, match=r"^Choose a Python file or paste some code\.$"):
        code_from_inputs(inputs)


def test_missing_file_names_it(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match=r"^Could not find gone\.py"):
        code_from_inputs({"source": CodeValue(tmp_path / "gone.py", "")})


def test_line_column_needs_a_code_source() -> None:
    with pytest.raises(ValueError, match="not a CodeSource"):
        PanelSpec(
            title="T",
            inputs=(TextArea(key="source", label="Code"),),
            outputs=(ResultsTable(key="t", line_column="Line"),),
        )
    PanelSpec(
        title="T",
        inputs=(CodeSource(key="source"),),
        outputs=(ResultsTable(key="t", line_column="Line"),),
    )


def test_a_code_source_choice_has_its_own_key() -> None:
    lang = Choice(key="from", label="Language", choices=(("py", "Python"), ("ocr", "OCR")))
    spec = PanelSpec(title="T", inputs=(CodeSource(key="source", choice=lang),))
    assert spec.input_keys() == ["source", "from"]
    with pytest.raises(ValueError, match="duplicate"):
        PanelSpec(
            title="T",
            inputs=(CodeSource(key="source", choice=lang), Choice("from", "F", (("a", "A"),))),
        )


# -- input() calls: the Inputs box's placeholder (#21) ------------------------
@pytest.mark.parametrize(
    ("source", "count", "repeats"),
    [
        ("print(1)\n", 0, ""),
        ("x = input()\n", 1, ""),
        ('a = int(input("A? "))\nb = input()\nprint(a, b)\n', 2, ""),
        # Both arms of an if count: the code shows two places that read a line.
        ("if True:\n    a = input()\nelse:\n    a = input()\n", 2, ""),
        ("for i in range(3):\n    x = input()\n", 1, "loop"),
        ("while input() != 'q':\n    pass\n", 1, "loop"),
        ("names = [input() for _ in range(3)]\n", 1, "loop"),
        ("def ask():\n    return input()\n\nask()\nask()\n", 1, "function"),
        # A method or another name called input is not the builtin.
        ("import sys\nx = sys.stdin.readline()\ny = obj.input()\n", 0, ""),
    ],
)
def test_count_input_calls(source: str, count: int, repeats: str) -> None:
    calls = count_input_calls(source)
    assert calls == InputCalls(count, repeats)  # type: ignore[arg-type]
    assert calls.at_least is bool(repeats)


def test_count_input_calls_of_broken_code_is_none() -> None:
    assert count_input_calls("if x\n    input()\n") is None


def test_inputs_placeholder_says_how_many_lines() -> None:
    assert inputs_placeholder("") == "No input() calls in this program:\nleave this empty"
    assert inputs_placeholder("x = input()\n") == "1 input() call:\none line"
    assert inputs_placeholder("a = input()\nb = input()\n") == "2 input() calls:\none line each"
    assert inputs_placeholder("for i in range(2):\n    a = input()\nb = input()\n") == (
        "At least 2 input() calls\n(in a loop): one line each"
    )
    assert inputs_placeholder("if x\n") == INPUTS_PLACEHOLDER
    # Each line of the placeholder fits the box at its narrowest.
    for source in ("for i in range(2):\n    a = input()\n", "def f():\n    input()\n"):
        assert all(len(line) <= 36 for line in inputs_placeholder(source).splitlines())


def test_input_calls_phrase() -> None:
    assert input_calls_phrase(InputCalls(1)) == "once"
    assert input_calls_phrase(InputCalls(2)) == "twice"
    assert input_calls_phrase(InputCalls(4)) == "4 times"
    assert input_calls_phrase(InputCalls(2, "function")) == "at least twice (one is in a function)"


def test_inspect_inputs_box_reads_the_code(tmp_path: Path) -> None:
    program = tmp_path / "ask.py"
    program.write_text("a = input()\nb = input()\n", encoding="utf-8")
    found = inspect_inputs_box({"source": CodeValue(program, "")})
    assert found.placeholders == {"stdin": "2 input() calls:\none line each"}
    pasted = inspect_inputs_box({"source": CodeValue(None, "x = input()\n")})
    assert pasted.placeholders == {"stdin": "1 input() call:\none line"}
    # No code yet, or a file that has gone: the panel keeps its own placeholder.
    assert inspect_inputs_box({"source": CodeValue(None, "")}).placeholders == {}
    assert inspect_inputs_box({"source": CodeValue(tmp_path / "gone.py", "")}).placeholders == {}
