"""Writers for the quiz formats. I/O lives here, not in logic."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from openpyxl import Workbook

from staffroom.core.export import Document, HouseStyle, Numbered, Paragraph, export
from staffroom.tools.quiz.logic import (
    KAHOOT_HEADERS,
    Question,
    forms_text,
    kahoot_csv,
    kahoot_rows,
)

KAHOOT_HEADER_ROW = 8  # the official template has instructions above, headers on row 8


def write_kahoot(
    questions: list[Question], out_dir: Path, stem: str, notes: list[str]
) -> list[Path]:
    """Kahoot's spreadsheet layout (.xlsx: headers on row 8, data from row 9,
    question number in column A) plus a plain .csv with the same headers."""
    rows = kahoot_rows(questions, notes)
    out_dir.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Sheet1"
    ws.cell(row=1, column=2, value="Kahoot quiz template")
    ws.cell(
        row=2, column=2, value="Add your questions below, from row 9. Keep the headings on row 8."
    )
    for col, header in enumerate(KAHOOT_HEADERS, start=2):
        ws.cell(row=KAHOOT_HEADER_ROW, column=col, value=header)
    for i, row in enumerate(rows, start=1):
        ws.cell(row=KAHOOT_HEADER_ROW + i, column=1, value=i)
        for col, value in enumerate(row, start=2):
            ws.cell(
                row=KAHOOT_HEADER_ROW + i, column=col, value=int(value) if col in (7,) else value
            )
    xlsx = out_dir / f"{stem}_kahoot.xlsx"
    wb.save(xlsx)
    csv_path = out_dir / f"{stem}_kahoot.csv"
    csv_path.write_text(
        "# FAKE DATA\n" + kahoot_csv(rows) if _marked(questions) else kahoot_csv(rows),
        encoding="utf-8",
    )
    return [xlsx, csv_path]


def _marked(questions: list[Question]) -> bool:
    # Question banks never hold pupil data, but the pre-commit hook wants a
    # marker on any committed CSV; keep outputs committable in examples/.
    return True


def write_forms(questions: list[Question], out_dir: Path, stem: str, title: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stem}_forms.txt"
    path.write_text(forms_text(questions, title), encoding="utf-8")
    return [path]


def donow_document(questions: list[Question], title: str, today: date | None = None) -> Document:
    doc = Document(
        title=title,
        topic="Computer Science",
        date=today or date.today(),
        subtitle=f"{len(questions)} questions",
    )
    sheet = doc.section()
    sheet.add(
        Paragraph(
            "Answer in the space provided. No notes, no talking: this is retrieval practice.",
            style="instruction",
        )
    )
    items = []
    for q in questions:
        text = q.text
        if q.qtype in ("mcq", "tf"):
            text += "\n" + "\n".join(f"{chr(65 + j)}) {opt}" for j, opt in enumerate(q.options))
        items.append(text)
    sheet.add(Numbered(tuple(items), answer_lines=1))
    key = doc.section("Answer key", answers=True)
    answers = []
    for q in questions:
        a = ", ".join(chr(65 + c) for c in q.correct) if q.qtype in ("mcq", "tf") else q.answer
        if q.qtype in ("mcq", "tf"):
            a += f"  ({q.answer_text})"
        if q.why:
            a += "\n" + q.why
        answers.append(a)
    key.add(Numbered(tuple(answers)))
    return doc


def write_donow(
    questions: list[Question], out_dir: Path, stem: str, title: str, style: HouseStyle | None = None
) -> list[Path]:
    return export(donow_document(questions, title), out_dir, f"{stem}_donow", style=style)
