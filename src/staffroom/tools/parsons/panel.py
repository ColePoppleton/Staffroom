"""Declarative UI for parsons."""

from __future__ import annotations

from staffroom.core.panel import (
    LogArea,
    OptionsForm,
    PanelSpec,
    ResourcePicker,
    TextArea,
    TextView,
)
from staffroom.tools.parsons.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Parsons",
        description="Working code → a Parsons problem worksheet and answer key.",
        inputs=(
            ResourcePicker(
                key="source",
                label="Python file",
                filter_ext=".py",
                help="From the library or anywhere. Or paste code below instead.",
                required=False,
            ),
            TextArea(
                key="pasted",
                label="Or paste code",
                placeholder="count = 0\nwhile count < 10:\n    print(count)\n    count += 1\n",
                help="Used when no file is chosen.",
                rows=8,
            ),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(TextView(key="preview", label="Preview (sheet, then key)"), LogArea()),
        run_label="Make worksheet",
    )
