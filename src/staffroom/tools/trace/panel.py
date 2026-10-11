"""Declarative UI for trace."""

from __future__ import annotations

from staffroom.core.panel import (
    OUTPUT_FORMAT_LABELS,
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
            OptionsForm(
                key="options",
                schema=Options,
                presets=PRESETS,
                # A dropdown, not a switch: the long field labels leave the
                # switch no room at the window's minimum width.
                choice_labels={"formats": OUTPUT_FORMAT_LABELS},
            ),
        ),
        outputs=(
            # Each step names its line: a row lights it in the program, and back.
            # On screen the table fits the pane (#16): a list set once and never
            # changed leaves for the line above, columns are as wide as their
            # values, a changed value is bold and a carried one grey, and Output
            # stays at the right edge. The printed sheet and key keep every column.
            ResultsTable(
                key="table",
                label="Completed table",
                line_column="Line",
                compact=True,
                lift_constants=True,
                mark_changes=True,
                pin_last=True,
            ),
            PagePreview(key="pages", label="Trace tables"),
            LogArea(),
        ),
        run_label="Trace",
    )
