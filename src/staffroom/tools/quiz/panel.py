"""Declarative UI for quiz: it starts from the bank (#17).

The bank as a chip with what was found in it; *Make* (the do-now first);
*Questions from* the topics the teacher picks, as the bank's own topics in
chips with counts, or from what was taught 1, 3 and 6 weeks ago (the taught
log and the date); then how many and the seed, with the spec-point filter
and the title under *More*. The CLI's flags build the same
:class:`~staffroom.tools.quiz.logic.Options`; :func:`options_from` folds the
panel's separate inputs into it."""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from staffroom.core.panel import (
    ChipChoice,
    Choice,
    FilePicker,
    LogArea,
    OptionsForm,
    PagePreview,
    PanelSpec,
    ResourcePicker,
    ResultsTable,
    TextField,
    TextView,
    shown_when,
)
from staffroom.tools.quiz.logic import Options

FORMAT_LABELS = {"donow": "Do-now sheet", "kahoot": "Kahoot", "forms": "Forms text"}
RUN_LABELS = {"donow": "Make do-now", "kahoot": "Make Kahoot", "forms": "Make Forms text"}
FROM_TOPICS, FROM_TAUGHT = "topics", "taught"
FROM_LABELS = {FROM_TOPICS: "Topics I pick", FROM_TAUGHT: "Taught 1, 3 and 6 weeks ago"}


def options_from(inputs: Mapping[str, Any]) -> Options:
    """The run's options: the form's (or the CLI's) :class:`Options`, with
    what the panel asks for separately folded in: *Make* (``fmt``),
    *Questions from* (``pick``), the topic chips (``topics``) and the date
    (``as_of``). A key the inputs do not hold leaves the field alone, so the
    CLI's ``{"source", "options"}`` runs exactly as it did."""
    options = inputs.get("options")
    if not isinstance(options, Options):
        options = Options()
    changes: dict[str, Any] = {}
    if "fmt" in inputs:
        changes["fmt"] = inputs["fmt"]
    if "pick" in inputs:
        changes["retrieval"] = inputs["pick"] == FROM_TAUGHT
    if "topics" in inputs:
        changes["topics"] = ",".join(inputs["topics"] or ())
    if "as_of" in inputs:
        changes["today"] = inputs["as_of"] or ""
    return dataclasses.replace(options, **changes)


def panel_spec() -> PanelSpec:
    from staffroom.tools.quiz.found import inspect_inputs

    defaults = Options()
    return PanelSpec(
        title="Quiz",
        description="One Markdown question bank → a printed do-now, Kahoot or Forms text.",
        inputs=(
            ResourcePicker(
                key="source",
                label="Question bank",
                filter_ext=".md",
                chip=True,
            ),
            # Do-now first: the weekly use, and checked on paper. Kahoot's
            # import is still to be confirmed (#1).
            Choice(
                key="fmt",
                label="Make",
                choices=tuple(FORMAT_LABELS.items()),
                default=defaults.fmt,
            ),
            Choice(key="pick", label="Questions from", choices=tuple(FROM_LABELS.items())),
            ChipChoice(
                key="topics",
                label="",
                empty_text="Choose a bank to see its topics.",
            ),
            FilePicker(
                key="taught_log",
                label="Taught log",
                filters=("CSV files (*.csv)", "All files (*)"),
                chip=True,
                help="Columns date,topic: one row per lesson. Topic and date only, never a "
                "class or a pupil.",
            ),
            TextField(
                key="as_of",
                label="As of",
                placeholder="Today, or a date such as 2026-10-12",
                max_length=10,
                required=False,
                counter=False,
            ),
            OptionsForm(
                key="options",
                schema=Options,
                label="",
                fields=("count", "seed", "spec", "title"),
                inline=("count", "seed"),
                more=("spec", "title"),
            ),
        ),
        joined=("topics", "taught_log", "as_of"),
        # Each source shows only what it reads; a hidden input is not handed
        # to the tool, and the log is not asked for unless it shows (#123).
        shown_when={
            "topics": shown_when("pick", FROM_TOPICS),
            "taught_log": shown_when("pick", FROM_TAUGHT),
            "as_of": shown_when("pick", FROM_TAUGHT),
        },
        inspect=inspect_inputs,
        outputs=(
            PagePreview(key="pages", label="Do-now"),
            ResultsTable(key="questions", label="Chosen questions"),
            # Kahoot rows or Forms text: what to paste or import (a do-now prints instead).
            TextView(key="paste", label="Paste text", copy_button=True, optional=True),
            LogArea(),
        ),
        run_label="Make",  # inspect names it: Make do-now, Make Kahoot, Make Forms text
    )
