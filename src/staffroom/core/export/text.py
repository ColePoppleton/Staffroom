"""Plain-text rendering: panel previews, the CLI and tests."""

from __future__ import annotations

from staffroom.core.export.model import (
    Code,
    Document,
    Heading,
    HintBox,
    Numbered,
    PageBreak,
    Paragraph,
    TableBlock,
)


def to_text(doc: Document, width: int = 78) -> str:
    out: list[str] = [doc.title, "=" * min(len(doc.title), width)]
    meta = "   ·   ".join(
        x for x in (doc.style.header, doc.topic, doc.date_text, doc.subtitle) if x
    )
    if meta:
        out.append(meta)
    out.append("")
    for section in doc.sections:
        if section.title:
            out += [section.title.upper(), "-" * min(len(section.title), width), ""]
        for block in section.blocks:
            out += _block(block)
    return "\n".join(out).rstrip() + "\n"


def _block(block: object) -> list[str]:
    if isinstance(block, Heading):
        return [block.text, "-" * len(block.text), ""]
    if isinstance(block, Paragraph):
        prefix = "» " if block.style == "instruction" else ""
        return [prefix + block.text, ""]
    if isinstance(block, Code):
        lines = ["    " + ln for ln in block.text.splitlines()]
        return [*([block.caption] if block.caption else []), *lines, ""]
    if isinstance(block, Numbered):
        items: list[str] = []
        for i, item in enumerate(block.items, block.start):
            first, *rest = item.splitlines() or [""]
            items.append(f"{i:>3}. {first}")
            items += ["     " + r for r in rest]
            items += ["     " + "_" * 60] * block.answer_lines
        return [*items, ""]
    if isinstance(block, TableBlock):
        widths = [
            max(len(c), *(len(r[i]) for r in block.rows)) if block.rows else len(c)
            for i, c in enumerate(block.columns)
        ]
        head = "  ".join(c.ljust(w) for c, w in zip(block.columns, widths, strict=True))
        rule = "  ".join("-" * w for w in widths)
        body = ["  ".join(v.ljust(w) for v, w in zip(r, widths, strict=True)) for r in block.rows]
        return [head, rule, *body, ""]
    if isinstance(block, HintBox):
        return [f"[{block.title}] {block.text}", ""]
    if isinstance(block, PageBreak):
        return ["", "- - - - - page break - - - - -", ""]
    return []
