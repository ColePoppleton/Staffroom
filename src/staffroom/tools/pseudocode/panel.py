"""Declarative UI for pseudocode: the source on the left with the language it
is in, the translation on the right, what could not be translated under it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from staffroom.core.panel import (
    Choice,
    CodeSource,
    CodeValue,
    LogArea,
    OptionsForm,
    PanelSpec,
    TextView,
)
from staffroom.tools.pseudocode import logic
from staffroom.tools.pseudocode.logic import Options

FROM = Choice(
    key="from",
    label="Language",
    choices=(("guess", "Guess"), ("python", "Python"), ("ocr", "OCR ERL"), ("aqa", "AQA")),
    default="guess",
    help="What the code is written in; worked out from the code when you choose or paste it.",
)
TO = Choice(
    key="to",
    label="To",
    choices=(("ocr", "OCR ERL"), ("aqa", "AQA"), ("python", "Python")),
    default="ocr",
)


def suggest(inputs: Mapping[str, Any]) -> dict[str, str]:
    """*From* follows the code picked or pasted (#62): the language it looks
    like (the code first, then the file name), or ``guess`` when there is no
    code or it cannot be told. If that is already the *To* language, *To*
    moves to another one, so the next run translates something."""
    code = inputs.get("source")
    text = code.text if isinstance(code, CodeValue) else ""
    name = code.path.name if isinstance(code, CodeValue) and code.path else ""
    guess = (logic.guess_dialect(text) if text.strip() else None) or logic.dialect_from_name(name)
    if guess is None:
        return {"from": "guess"}
    values: dict[str, str] = {"from": guess}
    if inputs.get("to") == guess:
        values["to"] = "ocr" if guess == "python" else "python"
    return values


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Pseudocode",
        description=(
            "Python ↔ OCR Exam Reference Language ↔ AQA pseudocode, GCSE subset. "
            "Anything that cannot be translated is listed, never dropped silently."
        ),
        inputs=(
            CodeSource(key="source", label="From", filter_ext=None, required=False, choice=FROM),
            TO,
            OptionsForm(key="options", schema=Options, label="Save", fields=("formats",)),
        ),
        outputs=(
            TextView(key="output", label="Translation", copy_button=True, code=True),
            TextView(
                key="report", label="Could not translate / notes", monospace=False, place="below"
            ),
            LogArea(),
        ),
        run_label="Translate",
        suggest=suggest,
    )
