"""Declarative UI for worksheet."""

from __future__ import annotations

from staffroom.core.panel import LogArea, OptionsForm, PanelSpec, TextView
from staffroom.tools.worksheet.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Worksheet",
        description=(
            "Seeded theory question sets with answer keys: binary, logic, file sizes, compression."
        ),
        inputs=(OptionsForm(key="options", schema=Options),),
        outputs=(TextView(key="preview", label="Preview (sheet, then key)"), LogArea()),
        run_label="Make worksheet",
    )
