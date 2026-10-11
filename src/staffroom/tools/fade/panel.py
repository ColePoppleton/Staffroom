"""Declarative UI for fade."""

from __future__ import annotations

from staffroom.core.panel import (
    OUTPUT_FORMAT_LABELS,
    CodeSource,
    LogArea,
    OptionsForm,
    PagePreview,
    PanelSpec,
    shown_when,
)
from staffroom.tools.fade.logic import Options

ORDER_LABELS = {
    "bottom_up": "Last lines first",
    "top_down": "First lines first",
    "ranges": "Only the lines I list",
}


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
            OptionsForm(
                key="options",
                schema=Options,
                shown_when={"ranges": shown_when("order", "ranges")},
                choice_labels={"order": ORDER_LABELS, "formats": OUTPUT_FORMAT_LABELS},
                switches=("formats",),
            ),
        ),
        outputs=(PagePreview(key="pages", label="Faded versions"), LogArea()),
        run_label="Make versions",
    )
