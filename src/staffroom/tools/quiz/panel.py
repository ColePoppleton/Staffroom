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
    shown_when,
)
from staffroom.tools.quiz.logic import Options

FORMAT_LABELS = {"kahoot": "Kahoot", "forms": "Forms", "donow": "Do now"}


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
            OptionsForm(
                key="options",
                schema=Options,
                # Kahoot rows carry no title; the date only steers retrieval mode.
                shown_when={
                    "title": shown_when("fmt", "forms", "donow"),
                    "today": shown_when("retrieval", True),
                },
                choice_labels={"fmt": FORMAT_LABELS},
                switches=("fmt",),
            ),
            # Under the form, so ticking Retrieval mode opens it below the
            # tick rather than pushing the form down (#123).
            FilePicker(
                key="taught_log",
                label="Taught log (.csv)",
                filters=("CSV files (*.csv)", "All files (*)"),
                help="Columns date,topic. Topic and date only: never a class or a pupil.",
            ),
        ),
        # The log is read only in retrieval mode: hidden otherwise, and not
        # handed to the tool (#123).
        shown_when={"taught_log": shown_when("options.retrieval", True)},
        outputs=(
            ResultsTable(key="chosen", label="Chosen questions"),
            PagePreview(key="pages", label="Do-now"),
            # Kahoot rows or Forms text: what to paste or import (a do-now prints instead).
            TextView(key="paste", label="Paste text", copy_button=True, optional=True),
            LogArea(),
        ),
        run_label="Export",
    )
