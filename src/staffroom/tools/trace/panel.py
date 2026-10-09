"""Declarative UI for trace."""

from __future__ import annotations

from staffroom.core.panel import (
    LogArea,
    OptionsForm,
    PanelSpec,
    ResourcePicker,
    ResultsTable,
    TextArea,
    TextView,
)
from staffroom.core.runner import limits_note
from staffroom.tools.trace.logic import PRESETS, TIMEOUT, Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Trace",
        description=(
            "Run a program step by step and produce blank and completed trace tables. "
            + limits_note(TIMEOUT)
        ),
        inputs=(
            ResourcePicker(
                key="source",
                label="Python file",
                filter_ext=".py",
                required=False,
                help="From the library or anywhere. Or paste code below instead.",
            ),
            TextArea(
                key="pasted", label="Or paste code", rows=8, help="Used when no file is chosen."
            ),
            TextArea(
                key="stdin",
                label="Inputs",
                rows=3,
                monospace=True,
                placeholder="One line per input() call",
                help="What the program reads from input(), one line each.",
            ),
            OptionsForm(key="options", schema=Options, presets=PRESETS),
        ),
        outputs=(
            ResultsTable(key="table", label="Completed trace table"),
            TextView(key="preview", label="Preview (sheet, then key)"),
            LogArea(),
        ),
        run_label="Trace",
    )
