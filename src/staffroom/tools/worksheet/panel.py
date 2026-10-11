"""Declarative UI for worksheet."""

from __future__ import annotations

from staffroom.core.panel import (
    OUTPUT_FORMAT_LABELS,
    LogArea,
    OptionsForm,
    PagePreview,
    PanelSpec,
    shown_when,
)
from staffroom.tools.worksheet.logic import TOPIC_TITLES, Options

DIFFICULTY_LABELS = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
LEVEL_LABELS = {"gcse": "GCSE", "a_level": "A level"}
LAW_LABELS = {
    "absorption": "Absorption",
    "de_morgan": "Absorption + De Morgan",
    "identities": "Identities",
    "all": "All laws",
}


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Worksheet",
        description=(
            "Seeded theory question sets with answer keys: binary, logic, file sizes, compression."
        ),
        inputs=(
            OptionsForm(
                key="options",
                schema=Options,
                # The gate level only matters to truth tables, the laws only to
                # simplification: every other topic hides them.
                shown_when={
                    "level": shown_when("topic", "truth_tables"),
                    "laws": shown_when("topic", "boolean_simplification"),
                },
                choice_labels={
                    "topic": TOPIC_TITLES,
                    "difficulty": DIFFICULTY_LABELS,
                    "level": LEVEL_LABELS,
                    "laws": LAW_LABELS,
                    "formats": OUTPUT_FORMAT_LABELS,
                },
                switches=("difficulty", "level", "formats"),
            ),
        ),
        outputs=(PagePreview(key="pages", label="Worksheet"), LogArea()),
        run_label="Make worksheet",
    )
