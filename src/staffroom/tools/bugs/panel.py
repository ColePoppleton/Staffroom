"""Declarative UI for bugs."""

from __future__ import annotations

from staffroom.core.panel import (
    OUTPUT_FORMAT_LABELS,
    CardList,
    CodeSource,
    LogArea,
    OptionsForm,
    PagePreview,
    PanelSpec,
    TextArea,
    Tone,
)
from staffroom.core.runner import limits_note
from staffroom.tools.bugs.logic import TIMEOUT, Options

# How loudly each outcome (logic.Outcome) speaks on its card: a crash or a
# hang stops the program, a wrong output gets past a pupil who does not check.
OUTCOME_TONES: tuple[tuple[str, Tone], ...] = (
    ("crash", "danger"),
    ("syntax_error", "danger"),
    ("hang", "danger"),
    ("wrong_output", "warning"),
    ("silent", "neutral"),
)


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Bugs",
        description=(
            "Inject one controlled error per copy of a working program; "
            "the key says what each does. " + limits_note(TIMEOUT)
        ),
        inputs=(
            CodeSource(key="source", label="Program", required=False),
            TextArea(
                key="stdin",
                label="Inputs",
                rows=3,
                placeholder="One line per input() call",
                help="Used when running the original and each variant to see what happens.",
            ),
            OptionsForm(
                key="options",
                schema=Options,
                # A dropdown, not a switch: the long field labels leave the
                # switch no room at the window's minimum width.
                choice_labels={"formats": OUTPUT_FORMAT_LABELS},
            ),
        ),
        outputs=(
            # One card per variant, its outcome as a badge, so what each bug
            # does is in view at any window width (#16). A card names the line
            # it broke: choosing it lights the line in the program, and back.
            CardList(
                key="key",
                label="What each bug does",
                title="Version {Version}",
                details=("line {Line}", "{Bug}"),
                badge="What happens",
                tone_column="Outcome",
                tones=OUTCOME_TONES,
                code_lines=(("was", "Original"), ("now", "Changed to")),
                line_column="Line",
            ),
            PagePreview(key="pages", label="Bug hunt"),
            LogArea(),
        ),
        run_label="Make variants",
    )
