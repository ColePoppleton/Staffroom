"""Declarative UI for trace."""

from __future__ import annotations

from teaching_tools.core.panel import (
    LogArea,
    OptionsForm,
    PanelSpec,
    ResourcePicker,
    ResultsTable,
    TextArea,
    TextView,
)
from teaching_tools.tools.trace.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Trace",
        description=(
            "Run a program step by step in a sandbox and produce blank and completed trace tables."
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
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(
            ResultsTable(key="table", label="Completed trace table"),
            TextView(key="preview", label="Preview (sheet, then key)"),
            LogArea(),
        ),
        run_label="Trace",
    )
