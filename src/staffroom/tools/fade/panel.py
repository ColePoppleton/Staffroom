"""Declarative UI for fade."""

from __future__ import annotations

from staffroom.core.panel import (
    LogArea,
    OptionsForm,
    PanelSpec,
    ResourcePicker,
    TextArea,
    TextView,
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
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(TextView(key="preview", label="Preview (sheet, then key)"), LogArea()),
        run_label="Make versions",
    )
