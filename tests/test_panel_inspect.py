"""The vocabulary #17 added: chips a tool fills from a file (``ChipChoice``
and ``PanelSpec.inspect``), inputs joined to the group above, and an options
form with fields on one row and fields under *More*."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from staffroom.core.panel import (
    ChipChoice,
    ChipOption,
    Choice,
    Found,
    Inspection,
    OptionsForm,
    PanelSpec,
    ResourcePicker,
    empty_values,
    shown_when,
)


@dataclass
class Opts:
    count: int = 10
    seed: int = 1
    spec: str = ""
    title: str = field(default="Do now", metadata={"label": "Title"})


def test_a_chip_choice_hands_over_the_chips_that_are_on() -> None:
    chips = ChipChoice(key="topics", label="Topics")
    assert empty_values(chips) == {"topics": ()}
    assert ChipOption("cpu").shown == "cpu"
    assert ChipOption("cpu", text="The CPU", count=2).shown == "The CPU"


def test_a_hidden_chip_choice_hands_over_none_on() -> None:
    spec = PanelSpec(
        title="T",
        inputs=(
            Choice(key="pick", label="From", choices=(("topics", "Topics"), ("log", "Log"))),
            ChipChoice(key="topics", label=""),
        ),
        shown_when={"topics": shown_when("pick", "topics")},
    )
    values = {"pick": "log", "topics": ("cpu",)}
    assert spec.hidden_inputs(values) == {"topics"}
    assert spec.passed(values)["topics"] == ()


def test_inspect_and_found_are_plain_data() -> None:
    found = Found()
    assert found.notes == () and found.rows is None and found.chips is None
    assert found.rows_label == "Preview rows"
    assert Inspection().found == {} and Inspection().run_label == ""

    def inspect(_values: object) -> Inspection:
        return Inspection(found={"bank": Found(chips=(ChipOption("cpu", count=2),))})

    spec = PanelSpec(
        title="T", inputs=(ResourcePicker(key="bank", label="Bank", chip=True),), inspect=inspect
    )
    assert spec.inspect is not None
    assert spec.inspect({})  # what the shell calls on every change


def test_joined_names_an_input_that_follows_another() -> None:
    a = ResourcePicker(key="a", label="A")
    b = ChipChoice(key="b", label="")
    assert PanelSpec(title="T", inputs=(a, b), joined=("b",)).joined == ("b",)
    with pytest.raises(ValueError, match="not an input"):
        PanelSpec(title="T", inputs=(a, b), joined=("c",))
    with pytest.raises(ValueError, match="first input"):
        PanelSpec(title="T", inputs=(a, b), joined=("a",))


def test_inline_and_more_name_fields_of_the_form() -> None:
    form = OptionsForm(key="o", schema=Opts, inline=("count", "seed"), more=("spec", "title"))
    assert form.inline == ("count", "seed") and form.more == ("spec", "title")
    with pytest.raises(ValueError, match="not a field"):
        OptionsForm(key="o", schema=Opts, more=("nope",))
    with pytest.raises(ValueError, match="not in its fields"):
        OptionsForm(key="o", schema=Opts, fields=("count", "seed"), more=("spec",))
    with pytest.raises(ValueError, match="two fields or more"):
        OptionsForm(key="o", schema=Opts, inline=("count",))
    with pytest.raises(ValueError, match="both inline and under More"):
        OptionsForm(key="o", schema=Opts, inline=("count", "seed"), more=("seed",))
    with pytest.raises(ValueError, match="inline fields always show"):
        OptionsForm(
            key="o",
            schema=Opts,
            inline=("count", "seed"),
            shown_when={"seed": shown_when("spec", "x")},
        )
