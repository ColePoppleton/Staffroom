"""Variants + key as a house-style Document."""

from __future__ import annotations

from datetime import date

from staffroom.core.codeinput import numbered_listing
from staffroom.core.export import Code, Document, PageBreak, Paragraph, TableBlock, sheet_date
from staffroom.tools.bugs.logic import INDENT_LEGEND, Variant, key_label, key_lines, shows_indent

PER_PAGE = 2  # variants per printed page; a page break only between pairs
SILENT_HINT = "this version may run the same: read the code"


def build_document(
    name: str,
    source: str,
    variants: list[Variant],
    today: date | None = None,
    seed: int | None = None,
) -> Document:
    count = f"{len(variants)} versions, one bug each"
    doc = Document(
        title=f"Find the bug: {name}",
        topic="Python",
        date=today or sheet_date(),
        subtitle=count if seed is None else f"seed {seed} · {count}",
    )
    sheet = doc.section()
    # Silent versions are only there when the teacher asked for them, and each
    # is flagged; otherwise every bug shows when the program runs.
    outcomes = (
        "crash, wrong output, or nothing visible"
        if any(v.silent for v in variants)
        else "crash or wrong output"
    )
    sheet.add(
        Paragraph(
            "Each version of the program has exactly one bug. Find the line, say what is "
            f"wrong, and predict what happens when it runs ({outcomes}).",
            style="instruction",
        )
    )
    for i, v in enumerate(variants):
        if i and i % PER_PAGE == 0:
            sheet.add(PageBreak())
        caption = f"Version {v.number}" + (f" ({SILENT_HINT})" if v.silent else "")
        sheet.add(Code(numbered_listing(v.source), caption=caption))
        sheet.add(
            Paragraph(
                "Line: ______   What is wrong: ____________________________   "
                "What happens: ______________"
            )
        )

    key = doc.section("Answer key", answers=True)
    lines = [key_lines(v.mutation) for v in variants]
    key.add(
        TableBlock(
            ("Version", "Line", "Bug", "Original", "Changed to", "What happens"),
            tuple(
                (str(v.number), str(v.mutation.line), key_label(v.mutation), old, new, v.outcome)
                for v, (old, new) in zip(variants, lines, strict=True)
            ),
            monospace=True,
        )
    )
    if shows_indent(lines):
        key.add(Paragraph(INDENT_LEGEND, style="muted"))
    key.add(Code(numbered_listing(source), caption="Original program"))
    return doc
