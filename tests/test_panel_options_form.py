"""``OptionsForm``'s shown_when, choice labels and switches, without Qt (#91)."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Literal

import pytest

from staffroom.core.panel import (
    OUTPUT_FORMAT_LABELS,
    OptionsForm,
    hidden_fields,
    shown_when,
)


class Mode(enum.Enum):
    FAST = "fast"
    CAREFUL = "careful"


@dataclass
class Opts:
    topic: Literal["binary", "logic"] = "binary"
    laws: Literal["absorption", "all"] = "absorption"
    strict: bool = False
    note: str = ""
    count: int = 3
    mode: Mode = Mode.FAST
    formats: Literal["both", "docx", "pdf"] = "both"


WHEN = {
    "laws": shown_when("topic", "logic"),
    "strict": shown_when("topic", "logic"),
    "note": shown_when("strict", True),
}


def test_hidden_fields_follow_their_conditions_and_what_they_hang_on() -> None:
    assert hidden_fields(WHEN, Opts()) == {"laws", "strict", "note"}
    assert hidden_fields(WHEN, Opts(topic="logic")) == {"note"}
    assert hidden_fields(WHEN, Opts(topic="logic", strict=True)) == set()
    # strict is ticked but hidden, so what hangs on it is hidden too.
    assert hidden_fields(WHEN, Opts(strict=True)) == {"laws", "strict", "note"}


def test_passed_puts_hidden_fields_back_to_their_defaults() -> None:
    form = OptionsForm(key="options", schema=Opts, shown_when=WHEN)
    held = Opts(laws="all", strict=True, note="x", count=7)
    assert form.passed(held) == Opts(count=7)
    shown = Opts(topic="logic", laws="all", strict=True, note="x")
    assert form.passed(shown) == shown


def test_label_for_falls_back_to_the_value() -> None:
    form = OptionsForm(
        key="options",
        schema=Opts,
        choice_labels={"formats": OUTPUT_FORMAT_LABELS, "mode": {"fast": "Quick"}},
    )
    assert form.label_for("formats", "both") == "Word + PDF"
    assert form.label_for("mode", Mode.FAST) == "Quick"
    assert form.label_for("mode", Mode.CAREFUL) == "careful"
    assert form.label_for("topic", "logic") == "logic"


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"shown_when": {"nope": shown_when("topic", "logic")}}, "'nope', not a field"),
        ({"shown_when": {"laws": shown_when("nope", 1)}}, "'nope', not a field"),
        ({"shown_when": {"laws": shown_when("topic", "logik")}}, "can never be ['logik']"),
        ({"shown_when": {"laws": shown_when("laws", "all")}}, "loops"),
        (
            {"shown_when": {"laws": shown_when("note", "x"), "note": shown_when("laws", "all")}},
            "loops",
        ),
        (
            {"fields": ("laws",), "shown_when": {"laws": shown_when("topic", "logic")}},
            "'topic', not in its fields",
        ),
        ({"choice_labels": {"count": {"3": "three"}}}, "'count', not a choice"),
        ({"choice_labels": {"formats": {"rtf": "RTF"}}}, "labels values it lacks: ['rtf']"),
        ({"switches": ("note",)}, "'note', not a choice"),
        ({"switches": ("nope",)}, "'nope', not a field"),
    ],
)
def test_a_form_that_cannot_work_is_refused(kwargs: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message.replace("[", r"\[").replace("]", r"\]")):
        OptionsForm(key="options", schema=Opts, **kwargs)  # type: ignore[arg-type]


def test_shown_when_needs_a_value() -> None:
    with pytest.raises(ValueError, match="at least one value"):
        shown_when("topic")
