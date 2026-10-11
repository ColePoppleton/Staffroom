from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Literal

from PySide6.QtWidgets import QComboBox
from pytestqt.qtbot import QtBot

from staffroom.core.panel import OUTPUT_FORMAT_LABELS, OptionsForm, preset, shown_when
from staffroom.shell.widgets import OptionsFormWidget
from staffroom.shell.widgets.choice import ChoiceWidget


class Mode(enum.Enum):
    FAST = "fast"
    CAREFUL = "careful"


@dataclass
class Opts:
    flag: bool = True
    count: int = field(default=3, metadata={"min": 0, "max": 10, "label": "How many"})
    ratio: float = 0.5
    name: str = "x"
    level: Literal["low", "high"] = "high"
    mode: Mode = Mode.CAREFUL


def test_form_round_trips_defaults(qtbot: QtBot) -> None:
    form = OptionsFormWidget(Opts)
    qtbot.addWidget(form)
    assert form.value() == Opts()


def test_form_reads_edits(qtbot: QtBot) -> None:
    form = OptionsFormWidget(Opts)
    qtbot.addWidget(form)
    form._getters  # noqa: B018 - ensure built
    widgets = {
        name: form.layout().itemAt(i * 2 + 1).widget()
        for i, name in enumerate(Opts.__dataclass_fields__)
    }
    widgets["flag"].setChecked(False)
    widgets["count"].setValue(7)
    widgets["ratio"].setValue(1.25)
    widgets["name"].setText("y")
    widgets["level"].setCurrentText("low")
    widgets["mode"].setCurrentIndex(0)
    assert form.value() == Opts(
        flag=False, count=7, ratio=1.25, name="y", level="low", mode=Mode.FAST
    )


PRESETS = (
    preset("Quick", flag=True, count=1),
    preset("Careful", flag=False, count=9, mode=Mode.CAREFUL),
)


def test_form_without_presets_has_no_preset_row(qtbot: QtBot) -> None:
    form = OptionsFormWidget(Opts)
    qtbot.addWidget(form)
    assert form.preset_combo is None and form.current_preset() == "Custom"
    assert list(form.widgets) == list(Opts.__dataclass_fields__)


def test_choosing_a_preset_sets_only_the_fields_it_pins(qtbot: QtBot) -> None:
    form = OptionsFormWidget(Opts, PRESETS)
    qtbot.addWidget(form)
    assert form.preset_combo is not None
    # Defaults (flag=True, count=3) match neither preset, so the form starts Custom.
    assert form.current_preset() == "Custom"
    assert [form.preset_combo.itemText(i) for i in range(form.preset_combo.count())] == [
        "Quick",
        "Careful",
        "Custom",
    ]
    form.widgets["name"].setText("kept")
    with qtbot.waitSignal(form.changed):
        form.preset_combo.setCurrentText("Careful")
    assert form.value() == Opts(flag=False, count=9, name="kept", mode=Mode.CAREFUL)
    assert form.current_preset() == "Careful"
    # A matching preset means Custom is not on offer.
    assert form.preset_combo.findText("Custom") < 0


def test_editing_a_field_moves_the_dropdown_to_the_matching_preset_or_custom(qtbot: QtBot) -> None:
    form = OptionsFormWidget(Opts, PRESETS)
    qtbot.addWidget(form)
    form.apply_preset("Quick")
    assert form.current_preset() == "Quick"
    with qtbot.waitSignal(form.changed):
        form.widgets["count"].setValue(2)
    assert form.current_preset() == "Custom" and form.value().count == 2
    form.widgets["count"].setValue(1)
    assert form.current_preset() == "Quick"
    # Fields no preset pins do not disturb the choice.
    form.widgets["ratio"].setValue(2.0)
    assert form.current_preset() == "Quick"
    form.apply_preset("not a preset")
    assert form.current_preset() == "Quick" and form.value().ratio == 2.0


# -- shown_when, choice labels and switches (#91) ----------------------------
@dataclass
class Sheet:
    topic: Literal["binary", "logic", "huffman"] = "binary"
    laws: Literal["absorption", "all"] = "absorption"
    strict: bool = False
    note: str = ""
    formats: Literal["both", "docx", "pdf"] = "both"
    mode: Mode = Mode.CAREFUL


SHEET_FORM = OptionsForm(
    key="options",
    schema=Sheet,
    shown_when={
        "laws": shown_when("topic", "logic"),
        "strict": shown_when("topic", "logic", "huffman"),
        # Only under a shown, ticked "strict": hidden when strict is hidden too.
        "note": shown_when("strict", True),
    },
    choice_labels={
        "topic": {"binary": "Binary numbers", "logic": "Logic"},
        "formats": OUTPUT_FORMAT_LABELS,
        "mode": {"fast": "Quick", "careful": "Careful"},
    },
    switches=("formats", "mode"),
)


def _sheet_form(qtbot: QtBot) -> OptionsFormWidget:
    form = OptionsFormWidget.for_spec(SHEET_FORM)
    qtbot.addWidget(form)
    return form


def test_a_field_shows_only_while_its_condition_holds(qtbot: QtBot) -> None:
    form = _sheet_form(qtbot)
    assert form.shown_fields() == ["topic", "formats", "mode"]
    with qtbot.waitSignal(form.changed):
        form.set_field("topic", "logic")
    assert form.shown_fields() == ["topic", "laws", "strict", "formats", "mode"]
    form.set_field("strict", True)
    assert "note" in form.shown_fields()
    # Hiding "strict" hides what depends on it, though strict is still ticked.
    form.set_field("topic", "binary")
    assert form.shown_fields() == ["topic", "formats", "mode"]


def test_a_hidden_field_keeps_its_value_but_the_tool_gets_the_default(qtbot: QtBot) -> None:
    form = _sheet_form(qtbot)
    form.set_field("topic", "logic")
    form.set_field("laws", "all")
    form.set_field("strict", True)
    form.set_field("note", "typed")
    assert form.value() == Sheet(topic="logic", laws="all", strict=True, note="typed")
    form.set_field("topic", "binary")
    assert form.value() == Sheet()  # nothing the teacher cannot see reaches the tool
    assert form.held().laws == "all" and form.held().note == "typed"
    form.set_field("topic", "logic")  # and it all comes back as it was
    assert form.value() == Sheet(topic="logic", laws="all", strict=True, note="typed")


def test_choices_show_their_labels_and_hand_back_their_values(qtbot: QtBot) -> None:
    form = _sheet_form(qtbot)
    topic = form.widgets["topic"]
    assert isinstance(topic, QComboBox)
    # A value with no label shows as itself.
    assert [topic.itemText(i) for i in range(topic.count())] == [
        "Binary numbers",
        "Logic",
        "huffman",
    ]
    topic.setCurrentIndex(1)
    assert form.value().topic == "logic"
    form.set_field("topic", "not a topic")  # unknown values leave the choice alone
    assert form.value().topic == "logic"


def test_switches_draw_a_segmented_switch(qtbot: QtBot) -> None:
    form = _sheet_form(qtbot)
    formats = form.widgets["formats"]
    assert isinstance(formats, ChoiceWidget)
    assert [b.text() for b in formats.buttons.values()] == ["Word + PDF", "Word", "PDF"]
    assert formats.buttons["both"].isChecked()
    with qtbot.waitSignal(form.changed):
        formats.buttons["pdf"].click()
    assert form.value().formats == "pdf"
    # An Enum switch hands back the member, and takes the member or its text.
    mode = form.widgets["mode"]
    assert isinstance(mode, ChoiceWidget)
    mode.buttons["fast"].click()
    assert form.value().mode is Mode.FAST
    form.set_field("mode", Mode.CAREFUL)
    assert form.value().mode is Mode.CAREFUL
    form.set_field("mode", "fast")
    assert form.value().mode is Mode.FAST


def test_a_preset_shows_the_fields_it_makes_apply(qtbot: QtBot) -> None:
    spec = OptionsForm(
        key="options",
        schema=Sheet,
        presets=(preset("Logic", topic="logic"),),
        shown_when=SHEET_FORM.shown_when,
    )
    form = OptionsFormWidget.for_spec(spec)
    qtbot.addWidget(form)
    assert "laws" not in form.shown_fields()
    form.apply_preset("Logic")
    assert "laws" in form.shown_fields()


def test_fields_and_shown_when_work_together(qtbot: QtBot) -> None:
    spec = OptionsForm(
        key="options",
        schema=Sheet,
        fields=("topic", "laws"),
        shown_when={"laws": shown_when("topic", "logic")},
    )
    form = OptionsFormWidget.for_spec(spec)
    qtbot.addWidget(form)
    assert form.shown_fields() == ["topic"]
    form.set_field("topic", "logic")
    assert form.shown_fields() == ["topic", "laws"]
