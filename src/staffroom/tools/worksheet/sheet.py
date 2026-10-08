"""Questions → a house-style Document (sheet + key)."""

from __future__ import annotations

from datetime import date

from staffroom.core.export import Document, Numbered, Paragraph, TableBlock
from staffroom.tools.worksheet.logic import TOPIC_TITLES, Options, Question, header_note


def build_document(
    questions: list[Question], options: Options, today: date | None = None, *, board: str = "ocr"
) -> Document:
    title = TOPIC_TITLES.get(options.topic, options.topic)
    subtitle = f"seed {options.seed} · {options.difficulty} · {len(questions)} questions"
    if note := header_note(options, board):
        subtitle += f" · {note}"  # the gate set or law family, so the sheet is self-describing
    doc = Document(
        title=f"Worksheet: {title}",
        topic="Computer Science",
        date=today or date.today(),
        subtitle=subtitle,
    )
    sheet = doc.section()
    sheet.add(
        Paragraph(
            "Show your working. Seed and settings are in the header so the set can be regenerated.",
            style="instruction",
        )
    )
    # Tables (truth tables) need their own block, so emit questions in runs.
    run: list[Question] = []
    number = 1

    def flush() -> None:
        nonlocal run, number
        if run:
            sheet.add(
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
        sheet.add(Numbered((q.prompt,), start=number, answer_lines=0))
        sheet.add(TableBlock(q.table[0], q.table[1:], monospace=True))
        number += 1
    flush()

    key = doc.section("Answer key", answers=True)
    items = []
    for q in questions:
        text = q.answer
        if q.working:
            text += "\n" + q.working
        items.append(text)
    key.add(Numbered(tuple(items)))
    return doc
