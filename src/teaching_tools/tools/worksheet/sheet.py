"""Questions → a house-style Document (sheet + key)."""

from __future__ import annotations

from datetime import date

from teaching_tools.core.export import Document, Numbered, Paragraph, TableBlock
from teaching_tools.tools.worksheet.logic import TOPIC_TITLES, Options, Question


def build_document(
    questions: list[Question], options: Options, today: date | None = None
) -> Document:
    title = TOPIC_TITLES.get(options.topic, options.topic)
    doc = Document(
        title=f"Worksheet: {title}",
        topic="Computer Science",
        date=today or date.today(),
        subtitle=f"seed {options.seed} · {options.difficulty} · {len(questions)} questions",
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
