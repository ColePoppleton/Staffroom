"""Faded versions as one house-style Document; the key is the solution."""

from __future__ import annotations

from datetime import date

from staffroom.core.codeinput import numbered_listing
from staffroom.core.export import Code, Document, PageBreak, Paragraph
from staffroom.tools.fade.logic import blank_count


def build_document(
    name: str, source: str, versions: list[str], today: date | None = None
) -> Document:
    doc = Document(
        title=f"Faded examples: {name}",
        topic="Python",
        date=today or date.today(),
        subtitle=f"{len(versions)} versions",
    )
    sheet = doc.section()
    sheet.add(
        Paragraph(
            "Each version blanks out more of the program than the last. "
            "Fill in every blank line so the program works exactly as before.",
            style="instruction",
        )
    )
    for i, version in enumerate(versions, 1):
        sheet.add(
            Code(
                numbered_listing(version),
                caption=f"Version {i} of {len(versions)}: {blank_count(version)} blank line(s)",
            )
        )
        if i < len(versions):
            sheet.add(PageBreak())
    key = doc.section("Answer key", answers=True)
    key.add(Code(numbered_listing(source), caption="Complete program"))
    return doc
