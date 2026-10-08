"""Variants + key as a house-style Document."""

from __future__ import annotations

from datetime import date

from staffroom.core.codeinput import numbered_listing
from staffroom.core.export import Code, Document, PageBreak, Paragraph, TableBlock
from staffroom.tools.bugs.logic import Variant


def build_document(
    name: str, source: str, variants: list[Variant], today: date | None = None
) -> Document:
    doc = Document(
        title=f"Find the bug: {name}",
        topic="Python",
        date=today or date.today(),
        subtitle=f"{len(variants)} versions, one bug each",
    )
    sheet = doc.section()
    sheet.add(
        Paragraph(
            "Each version of the program has exactly one bug. Find the line, say what is "
            "wrong, and predict what happens when it runs "
            "(crash, wrong output, or nothing visible).",
            style="instruction",
        )
    )
    for v in variants:
        sheet.add(Code(numbered_listing(v.source), caption=f"Version {v.number}"))
        sheet.add(
            Paragraph(
                "Line: ______   What is wrong: ____________________________   "
                "What happens: ______________"
            )
        )
        if v is not variants[-1]:
            sheet.add(PageBreak())

    key = doc.section("Answer key", answers=True)
    key.add(
        TableBlock(
            ("Version", "Line", "Bug", "Original", "Changed to", "What happens"),
            tuple(
                (
                    str(v.number),
                    str(v.mutation.line),
                    v.mutation.label,
                    v.mutation.original.strip(),
                    v.mutation.mutated.strip(),
                    v.outcome,
                )
                for v in variants
            ),
            monospace=True,
        )
    )
    key.add(Code(numbered_listing(source), caption="Original program"))
    return doc
