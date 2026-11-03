"""Declarative UI for pseudocode: the source on the left with the language it
is in, the translation on the right, what could not be translated under it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from staffroom.core.config import load_config
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
TO_CHOICES = (("ocr", "OCR ERL"), ("aqa", "AQA"), ("python", "Python"))
#: The language each exam board writes algorithms in. Pearson Edexcel 1CP2 has no
#: pseudocode of its own: its papers use Python 3 within the published Programming
#: Language Subset (PLS), and its specification calls pseudocode "informal".
BOARD_TARGETS: dict[str, logic.Target] = {"ocr": "ocr", "aqa": "aqa", "edexcel": "python"}
EDEXCEL_HELP = (
    "Pearson Edexcel 1CP2 assesses algorithms in Python (its Programming Language "
    "Subset), so To starts on Python."
)


def to_choice(board: str) -> Choice:
    """*To* starts on the language the teacher's exam board (Settings) uses;
    an unknown board starts on OCR ERL, as before."""
    target = BOARD_TARGETS.get(board.lower(), "ocr")
    help_ = EDEXCEL_HELP if board.lower() == "edexcel" else ""
    return Choice(key="to", label="To", choices=TO_CHOICES, default=target, help=help_)


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
    board = load_config().general.board
    return PanelSpec(
        title="Pseudocode",
        description=(
            "Python ↔ OCR Exam Reference Language ↔ AQA pseudocode, GCSE subset. "
            "Anything that cannot be translated is listed, never dropped silently."
        ),
        inputs=(
            CodeSource(
                key="source",
                label="From",
                filter_ext=(".py", ".txt"),  # Python, or pseudocode in a text file
                required=False,
                choice=FROM,
            ),
            to_choice(board),
            OptionsForm(
                key="options",
                schema=Options,
                label="Save",
                fields=("formats",),
                choice_labels={"formats": {"txt": "Text file", "none": "Don't save"}},
                switches=("formats",),
            ),
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
