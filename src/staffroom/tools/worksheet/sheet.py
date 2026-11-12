"""Questions → a house-style Document (sheet + key).

``build_review`` is the sheet as it was before lessons (#75), block for block, so an old
seed makes the same sheet; ``build_lesson`` lays out a lesson: aim, worked example, then
Warm-up, Practice and Stretch, numbered straight through.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from staffroom.core.export import (
    Document,
    Heading,
    Numbered,
    Paragraph,
    Section,
    TableBlock,
    WorkedExample,
    sheet_date,
)
from staffroom.tools.worksheet.lessons import (
    UNIT_BY_SLUG,
    Lesson,
    LessonSheet,
    Settings,
    lesson_note,
    make_lesson,
    spec_line,
)
from staffroom.tools.worksheet.logic import (
    MAX_COUNT,
    MIN_COUNT,
    TOPIC_TITLES,
    Difficulty,
    Question,
    generate,
    header_note,
)


def _questions(section: Section, questions: list[Question], start: int = 1) -> int:
    """Add the questions in runs: a truth table needs its own block. Returns the next
    question number."""
    run: list[Question] = []
    number = start

    def flush() -> None:
        nonlocal run, number
        if run:
            section.add(
                Numbered(
                    tuple(q.prompt for q in run),
                    start=number,
                    answer_lines=max(q.answer_lines for q in run),
                )
            )
            number += len(run)
            run = []

    for q in questions:
        if q.table is None:
            run.append(q)
            continue
        flush()
        section.add(Numbered((q.prompt,), start=number, answer_lines=0))
        section.add(TableBlock(q.table[0], q.table[1:], monospace=True))
        number += 1
    flush()
    return number


def _key(doc: Document, questions: list[Question]) -> None:
    key = doc.section("Answer key", answers=True)
    items = []
    for q in questions:
        text = q.answer
        if q.working:
            text += "\n" + q.working
        items.append(text)
    key.add(Numbered(tuple(items)))


def build_review(
    questions: list[Question],
    topic: str,
    seed: int,
    difficulty: Difficulty,
    settings: Settings,
    today: date | None = None,
) -> Document:
    """The sheet an old topic made before lessons, unchanged."""
    title = TOPIC_TITLES.get(topic, topic)
    subtitle = f"seed {seed} · {difficulty} · {len(questions)} questions"
    note = header_note(topic, settings.board, settings.level, settings.laws, difficulty)
    if note:
        subtitle += f" · {note}"  # the gate set or law family, so the sheet is self-describing
    doc = Document(
        title=f"Worksheet: {title}",
        topic="Computer Science",
        date=today or sheet_date(),
        subtitle=subtitle,
    )
    sheet = doc.section()
    sheet.add(
        Paragraph(
            "Show your working. Seed and settings are in the header so the set can be regenerated.",
            style="instruction",
        )
    )
    _questions(sheet, questions)
    _key(doc, questions)
    return doc


def lesson_title(lesson: Lesson) -> str:
    return f"{UNIT_BY_SLUG[lesson.unit].title}: {lesson.title}"


def build_lesson(
    content: LessonSheet,
    lesson: Lesson,
    seed: int,
    difficulty: Difficulty,
    settings: Settings,
    board_names: Mapping[str, str],
    today: date | None = None,
) -> Document:
    """A lesson sheet. The header names the board's spec point (or where the lesson
    belongs), then seed, difficulty and count, so the sheet can be made again."""
    questions = content.questions
    parts = [
        spec_line(lesson, settings.board, board_names),
        f"seed {seed}",
        difficulty,
        f"{len(questions)} questions",
    ]
    if note := lesson_note(lesson, settings, difficulty):
        parts.append(note)
    doc = Document(
        title=lesson_title(lesson),
        topic="Computer Science",
        date=today or sheet_date(),
        subtitle=" · ".join(parts),
    )
    sheet = doc.section()
    sheet.add(Paragraph(f"Aim: {content.aim}", style="instruction"))
    ex = content.example
    table = TableBlock(ex.table[0], ex.table[1:], monospace=True) if ex.table else None
    sheet.add(WorkedExample(ex.question, ex.steps, ex.answer, table))
    number = 1
    for part in content.parts:
        sheet.add(Heading(f"{part.name} · {part.hint}" if part.hint else part.name, level=2))
        number = _questions(sheet, list(part.questions), number)
    _key(doc, questions)
    return doc


@dataclass(frozen=True)
class Made:
    doc: Document
    questions: list[Question]
    stem: str  # the files' name: an old topic's Review keeps its old name
    note: str  # the gates or laws the header states, "" when none


def make_document(
    lesson: Lesson,
    seed: int,
    count: int,
    difficulty: Difficulty,
    settings: Settings,
    board_names: Mapping[str, str],
    today: date | None = None,
) -> Made:
    """The whole sheet and key for a lesson. ValueError for a count out of range."""
    if not MIN_COUNT <= count <= MAX_COUNT:
        msg = f"Questions must be between {MIN_COUNT} and {MAX_COUNT} (you asked for {count})."
        raise ValueError(msg)
    a_level = "_alevel" if settings.level == "a_level" else ""  # GCSE files keep their name
    if lesson.review:  # the sheet the old topic made: same seed, same questions
        questions = generate(
            lesson.legacy,
            seed,
            count,
            difficulty,
            board=settings.board,
            level=settings.level,
            laws=settings.laws,
        )
        return Made(
            build_review(questions, lesson.legacy, seed, difficulty, settings, today),
            questions,
            f"{lesson.legacy}_{difficulty}{a_level}_s{seed}",
            header_note(lesson.legacy, settings.board, settings.level, settings.laws, difficulty),
        )
    content = make_lesson(lesson, seed, count, difficulty, settings)
    level = a_level if "level" in lesson.uses else ""
    return Made(
        build_lesson(content, lesson, seed, difficulty, settings, board_names, today),
        content.questions,
        f"{lesson.unit}_{lesson.slug}".replace("-", "_") + f"_{difficulty}{level}_s{seed}",
        lesson_note(lesson, settings, difficulty),
    )
