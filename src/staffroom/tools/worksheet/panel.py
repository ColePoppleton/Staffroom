"""Declarative UI for worksheet: a unit, a lesson in it, then the sheet's settings."""

from __future__ import annotations

from staffroom.core import spec
from staffroom.core.config import Config
from staffroom.core.panel import (
    OUTPUT_FORMAT_LABELS,
    Choice,
    GroupedChoice,
    GroupedItem,
    ItemGroup,
    LogArea,
    OptionsForm,
    PagePreview,
    PanelSpec,
    shown_when,
)
from staffroom.tools.worksheet.lessons import (
    DEFAULT_LESSON,
    LESSONS,
    UNITS,
    off_board_reason,
    on_board,
)
from staffroom.tools.worksheet.logic import Options

DIFFICULTY_LABELS = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}
LEVEL_CHOICE = Choice(
    key="level",
    label="Gates",
    choices=(("gcse", "My GCSE board"), ("a_level", "A level")),
    help="A level adds XOR, and NAND/NOR at Hard",
)
LAWS_CHOICE = Choice(
    key="laws",
    label="Boolean laws",
    choices=(
        ("absorption", "Absorption"),
        ("de_morgan", "+ De Morgan"),
        ("identities", "Identities"),
        ("all", "All"),
    ),
    help="Identities allows X AND X, NOT NOT X and 0/1 on the sheet",
)


def lesson_choice(board: str) -> GroupedChoice:
    """Units as chips, lessons as rows with the board's spec point at the right. A
    lesson the board does not have stays choosable, greyed, saying whose it is."""
    name = spec.SHORT_NAMES.get(board, board.upper())
    groups = []
    for unit in UNITS:
        items = []
        for i, lesson in enumerate(unit.lessons):
            on = on_board(lesson, board)
            items.append(
                GroupedItem(
                    value=lesson.key,
                    text=lesson.title,
                    tag="mixed" if lesson.review else f"{name} {lesson.spec.get(board, '')}",
                    detail=lesson.what,
                    dim=not on,
                    note=off_board_reason(lesson, board, spec.SHORT_NAMES),
                    divided=lesson.review and not unit.lessons[i - 1].review,
                )
            )
        lessons_on = [les for les in unit.lessons if not les.review and on_board(les, board)]
        groups.append(
            ItemGroup(
                unit.slug,
                unit.title,
                tuple(items),
                dim=not lessons_on,
                note="" if lessons_on else f"Not on {name} GCSE",
            )
        )

    def again(config: Config) -> GroupedChoice:
        return lesson_choice(config.general.board)

    return GroupedChoice(
        key="lesson",
        label="Unit",
        items_label="Lesson",
        groups=tuple(groups),
        default=DEFAULT_LESSON,
        note=f"Spec points follow your board in Settings: {spec.BOARDS.get(board, board)}.",
        for_config=again,
    )


def _using(setting: str) -> tuple[str, ...]:
    return tuple(key for key, lesson in LESSONS.items() if setting in lesson.uses)


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Worksheet",
        description="Lesson sheets with answer keys: binary, logic, file sizes, compression.",
        inputs=(
            lesson_choice("ocr"),  # the shell rebuilds it for the teacher's board
            LEVEL_CHOICE,
            LAWS_CHOICE,
            OptionsForm(
                key="options",
                schema=Options,
                choice_labels={
                    "difficulty": DIFFICULTY_LABELS,
                    "formats": OUTPUT_FORMAT_LABELS,
                },
                switches=("difficulty", "formats"),
                inline=("count", "seed"),
            ),
        ),
        # The gate level only matters to truth tables, the laws only to simplification.
        shown_when={
            "level": shown_when("lesson", *_using("level")),
            "laws": shown_when("lesson", *_using("laws")),
        },
        joined=("level", "laws"),
        outputs=(PagePreview(key="pages", label="Worksheet"), LogArea()),
        run_label="Make lesson sheet",
    )
