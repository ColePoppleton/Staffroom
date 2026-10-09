"""Declarative UI for bugs."""

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
from staffroom.tools.bugs.logic import TIMEOUT, Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Bugs",
        description=(
            "Inject one controlled error per copy of a working program; "
            "the key says what each does. " + limits_note(TIMEOUT)
        ),
        inputs=(
            CodeSource(key="source", label="Program", required=False),
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
            # Each variant names the line it broke: a row lights it in the program.
            ResultsTable(key="key", label="What each bug does", line_column="Line"),
            PagePreview(key="pages", label="Bug hunt"),
            LogArea(),
        ),
        run_label="Make variants",
    )
