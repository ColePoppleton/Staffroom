"""Declarative UI for bugs."""

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
from staffroom.tools.bugs.logic import TIMEOUT, Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Bugs",
        description=(
            "Inject one controlled error per copy of a working program; "
            "the key says what each does. " + limits_note(TIMEOUT)
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
                placeholder="One line per input() call",
                help="Used when running the original and each variant to see what happens.",
            ),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(
            ResultsTable(key="key", label="Key"),
            TextView(key="preview", label="Preview (sheet, then key)"),
            LogArea(),
        ),
        run_label="Make variants",
    )
