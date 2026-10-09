from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Literal

from pytestqt.qtbot import QtBot

from staffroom.core.panel import preset
from staffroom.shell.widgets import OptionsFormWidget


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
