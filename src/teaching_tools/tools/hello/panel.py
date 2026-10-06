"""Declarative UI for hello."""

from __future__ import annotations

from teaching_tools.core.panel import (
    FilePicker,
    LogArea,
    OptionsForm,
    PanelSpec,
    ResultsTable,
    TablePreview,
)
from teaching_tools.tools.hello.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Hello",
        description="Reads a class list and writes it back with an Initials column.",
        inputs=(
            FilePicker(
                key="source",
                label="Class list",
                help="A CSV or XLSX with Forename and Surname columns.",
            ),
            TablePreview(key="preview", source="source", label="Class list preview"),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(ResultsTable(key="result", label="With initials"), LogArea()),
        run_label="Add initials",
    )
