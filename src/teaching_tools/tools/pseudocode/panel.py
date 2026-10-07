"""Declarative UI for pseudocode."""

from __future__ import annotations

from teaching_tools.core.panel import (
    LogArea,
    OptionsForm,
    PanelSpec,
    ResourcePicker,
    TextArea,
    TextView,
)
from teaching_tools.tools.pseudocode.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Pseudocode",
        description=(
            "Python ↔ OCR Exam Reference Language ↔ AQA pseudocode, GCSE subset. "
            "Anything that cannot be translated is listed, never dropped silently."
        ),
        inputs=(
            ResourcePicker(
                key="source",
                label="File",
                required=False,
                help="A .py or pseudocode text file from the library or anywhere. Or paste below.",
            ),
            TextArea(
                key="pasted", label="Or paste code", rows=12, help="Used when no file is chosen."
            ),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(
            TextView(key="output", label="Translation", copy_button=True),
            TextView(key="report", label="Could not translate / notes", monospace=False),
            LogArea(),
        ),
        run_label="Translate",
    )
