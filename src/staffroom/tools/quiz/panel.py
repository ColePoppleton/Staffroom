"""Declarative UI for quiz."""

from __future__ import annotations

from staffroom.core.panel import (
    FilePicker,
    LogArea,
    OptionsForm,
    PagePreview,
    PanelSpec,
    ResourcePicker,
    ResultsTable,
    TextView,
)
from staffroom.tools.quiz.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Quiz",
        description=(
            "A Markdown question bank tagged with spec points → Kahoot, Forms paste text or a "
            "printable do-now. Retrieval mode picks from topics taught 1, 3 and 6 weeks ago."
        ),
        inputs=(
            ResourcePicker(
                key="source",
                label="Question bank (.md)",
                filter_ext=".md",
                help="From the library or anywhere. See examples/question_bank.md for the format.",
            ),
            FilePicker(
                key="taught_log",
                label="Taught log (.csv) for retrieval mode",
                filters=("CSV files (*.csv)", "All files (*)"),
                help="Columns date,topic. Topic and date only: never a class or a pupil.",
                required=False,
            ),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(
            ResultsTable(key="chosen", label="Chosen questions"),
            PagePreview(key="pages", label="Do-now"),
            # Kahoot rows or Forms text: what to paste or import (a do-now prints instead).
            TextView(key="paste", label="Paste text", copy_button=True, optional=True),
            LogArea(),
        ),
        run_label="Export",
    )
