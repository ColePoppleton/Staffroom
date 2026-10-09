"""core.codeinput: the one place a code tool's input becomes source text, and
the CodeSource vocabulary it reads (#86)."""

from __future__ import annotations

from pathlib import Path

import pytest

from staffroom.core.codeinput import code_from_inputs, code_path
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
