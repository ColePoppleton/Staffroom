"""Declarative UI for parsons."""

from __future__ import annotations

from staffroom.core.panel import (
    CodeSource,
    LogArea,
    OptionsForm,
    PagePreview,
    PanelSpec,
)
from staffroom.tools.parsons.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Parsons",
        description="Working code → a Parsons problem worksheet and answer key.",
        inputs=(
            CodeSource(key="source", label="Working program", required=False),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(PagePreview(key="pages", label="Parsons problem"), LogArea()),
        run_label="Make worksheet",
    )
