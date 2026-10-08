from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Literal

from pytestqt.qtbot import QtBot

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
