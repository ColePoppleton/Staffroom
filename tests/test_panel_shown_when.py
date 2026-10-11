"""``PanelSpec.shown_when``: whole inputs that show only while they apply,
without Qt (#123)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest

from staffroom.core.panel import (
    Choice,
    CodeSource,
    CodeValue,
    Column,
    EditableTable,
    FilePicker,
    OptionsForm,
    PanelSpec,
    ShownWhen,
    TablePreview,
    TextField,
    empty_values,
    shown_when,
)
from staffroom.core.table import Table


@dataclass
class Opts:
    mode: Literal["plain", "retrieval"] = "plain"
    strict: bool = False
    note: str = ""


MODE = Choice(key="kind", label="Kind", choices=(("a", "A"), ("b", "B")))
INPUTS = (
    OptionsForm(key="options", schema=Opts, shown_when={"strict": shown_when("mode", "retrieval")}),
    MODE,
    FilePicker(key="taught", label="Taught log"),
    TextField(key="label", label="Label"),
)


def spec(when: dict[str, ShownWhen], inputs: tuple[Any, ...] = INPUTS) -> PanelSpec:
    return PanelSpec(title="T", inputs=inputs, shown_when=when)


def test_an_input_follows_a_form_field() -> None:
    panel = spec({"taught": shown_when("options.mode", "retrieval")})
    assert panel.hidden_inputs({"options": Opts()}) == {"taught"}
    assert panel.hidden_inputs({"options": Opts(mode="retrieval")}) == set()
    assert panel.hidden_inputs({}) == {"taught"}  # no value: the form's defaults


def test_an_input_follows_a_choice() -> None:
    panel = spec({"label": shown_when("kind", "b")})
    assert panel.hidden_inputs({"kind": "a"}) == {"label"}
    assert panel.hidden_inputs({"kind": "b"}) == set()
    assert panel.hidden_inputs({}) == {"label"}  # the choice's initial value


def test_reading_a_hidden_field_or_input_hides_it_too() -> None:
    # strict is ticked but its form hides it (mode is plain), so log hides.
    panel = spec({"taught": shown_when("options.strict", True), "label": shown_when("kind", "b")})
    assert panel.hidden_inputs({"options": Opts(strict=True), "kind": "b"}) == {"taught"}
    assert (
        panel.hidden_inputs({"options": Opts(mode="retrieval", strict=True), "kind": "b"}) == set()
    )


def test_a_hidden_input_hands_the_tool_its_empty_value() -> None:
    panel = spec(
        {"taught": shown_when("options.mode", "retrieval"), "label": shown_when("kind", "b")}
    )
    held = {"options": Opts(), "kind": "a", "taught": Path("taught.csv"), "label": "P3"}
    assert panel.passed(held) == {"options": Opts(), "kind": "a", "taught": None, "label": ""}
    shown = {**held, "options": Opts(mode="retrieval"), "kind": "b"}
    assert panel.passed(shown) == shown


def test_empty_values_by_widget() -> None:
    choice = Choice(key="unit", label="Unit", choices=(("pct", "%"), ("raw", "Raw")), default="raw")
    grid = EditableTable(key="g", label="G", columns=(Column("A"),), rows=(("x",),), choice=choice)
    assert empty_values(grid) == {"g": Table(["A"], [["x"]]), "unit": "raw"}
    assert empty_values(CodeSource(key="source")) == {"source": CodeValue(None, "")}
    assert empty_values(INPUTS[0]) == {"options": Opts()}
    assert empty_values(MODE) == {"kind": "a"}
    assert empty_values(TablePreview(key="p", source="taught")) == {}


@pytest.mark.parametrize(
    ("when", "message"),
    [
        ({"nope": shown_when("options.mode", "plain")}, "names no input"),
        ({"taught": shown_when("mode", "plain")}, "neither '<form key>.<field>'"),
        ({"taught": shown_when("other.mode", "plain")}, "neither '<form key>.<field>'"),
        ({"taught": shown_when("options.nope", 1)}, "'nope' is not a field of its form"),
        ({"taught": shown_when("options.mode", "retreival")}, "can never be ['retreival']"),
        ({"taught": shown_when("kind", "c")}, "can never be ['c']"),
        ({"options": shown_when("options.strict", True)}, "loops"),
    ],
)
def test_conditions_that_cannot_work_are_refused(when: dict[str, ShownWhen], message: str) -> None:
    with pytest.raises(ValueError, match=message.replace("[", r"\[").replace("]", r"\]")):
        spec(when)


def test_a_field_left_out_of_the_form_cannot_be_read() -> None:
    form = OptionsForm(key="options", schema=Opts, fields=("strict",))
    with pytest.raises(ValueError, match="'mode' is not a field of its form"):
        spec({"taught": shown_when("options.mode", "plain")}, (form, INPUTS[2]))


def test_an_inner_choice_can_steer_another_input_but_not_its_own() -> None:
    choice = Choice(key="lang", label="Language", choices=(("py", "Python"), ("ocr", "OCR")))
    code = CodeSource(key="source", choice=choice)
    panel = spec({"label": shown_when("lang", "ocr")}, (code, INPUTS[3]))
    assert panel.hidden_inputs({"lang": "py"}) == {"label"}
    with pytest.raises(ValueError, match="loops"):
        spec({"source": shown_when("lang", "ocr")}, (code,))


def test_a_compact_preview_follows_its_picker_only() -> None:
    preview = TablePreview(key="p", source="taught", compact=True)
    with pytest.raises(ValueError, match="compact TablePreview"):
        spec({"p": shown_when("kind", "b")}, (*INPUTS, preview))


def test_a_loop_between_two_inputs_is_refused() -> None:
    a = Choice(key="a", label="A", choices=(("x", "X"), ("y", "Y")))
    b = Choice(key="b", label="B", choices=(("x", "X"), ("y", "Y")))
    with pytest.raises(ValueError, match="loops"):
        spec({"a": shown_when("b", "x"), "b": shown_when("a", "x")}, (a, b))


def test_quiz_shows_its_taught_log_only_when_questions_come_from_it() -> None:
    from staffroom.tools.quiz.panel import panel_spec

    quiz = panel_spec()
    assert quiz.hidden_inputs({}) == {"taught_log", "as_of"}  # Topics I pick, by default
    on = {"pick": "taught", "taught_log": Path("log.csv"), "topics": ("cpu",)}
    assert quiz.hidden_inputs(on) == {"topics"}
    assert quiz.passed(on)["topics"] == ()
    off = {"pick": "topics", "taught_log": Path("log.csv"), "as_of": "2026-10-08"}
    assert quiz.passed(off)["taught_log"] is None and quiz.passed(off)["as_of"] == ""
