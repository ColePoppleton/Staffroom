"""Declarative UI for fade."""

from __future__ import annotations

from teaching_tools.core.panel import (
    LogArea,
    OptionsForm,
    PanelSpec,
    ResourcePicker,
    TextArea,
    TextView,
)
from teaching_tools.tools.fade.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Fade",
        description="A worked solution → progressively faded versions for pupils to complete.",
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
