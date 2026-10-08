"""Declarative UI for hello."""

from __future__ import annotations

from staffroom.core.panel import (
    FilePicker,
    LogArea,
    OptionsForm,
    PanelSpec,
    ResultsTable,
    TablePreview,
)
from staffroom.tools.hello.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Hello",
        description="Reads a marks file (one row per script, q1..qn) and adds a Total column.",
        inputs=(
            FilePicker(
                key="source",
                label="Marks file",
                help="CSV or XLSX with one column per question. Identifier columns are dropped.",
            ),
            TablePreview(key="preview", source="source", label="Marks preview"),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(ResultsTable(key="result", label="With totals"), LogArea()),
        run_label="Add totals",
    )
