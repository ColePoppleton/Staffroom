"""Declarative UI for trace."""

from __future__ import annotations

from staffroom.core.panel import (
    CodeSource,
    LogArea,
    OptionsForm,
    PagePreview,
    PanelSpec,
    ResultsTable,
    TextArea,
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
            CodeSource(key="source", label="Program", required=False),
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
            # Each step names its line: a row lights it in the program, and back.
            ResultsTable(key="table", label="Completed table", line_column="Line"),
            PagePreview(key="pages", label="Trace tables"),
            LogArea(),
        ),
        run_label="Trace",
    )
