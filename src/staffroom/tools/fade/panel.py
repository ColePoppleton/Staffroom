"""Declarative UI for fade."""

from __future__ import annotations

from staffroom.core.panel import (
    CodeSource,
    LogArea,
    OptionsForm,
    PagePreview,
    PanelSpec,
)
from staffroom.tools.fade.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Fade",
        description=(
            "A worked solution → progressively faded versions for pupils to complete. "
            "Nothing is run: the solution is blanked out as text "
            "(see Running pupil code in the docs for the tools that do run it)."
        ),
        inputs=(
            CodeSource(key="source", label="Worked solution", required=False),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(PagePreview(key="pages", label="Faded versions"), LogArea()),
        run_label="Make versions",
    )
