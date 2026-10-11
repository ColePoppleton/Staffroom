"""The house style: one document model rendered to docx, PDF or plain text.

Every worksheet, key and report in the project goes through here so they all
look the same: a header with title, topic and date (today's, or
``STAFFROOM_DATE`` for reproducible renders: see ``dating``); a footer with page
numbers; monospace blocks for code; answer sections that split off into a
separate key file.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from staffroom.core.export.dating import DATE_ENV, sheet_date
from staffroom.core.export.docx import write_docx
from staffroom.core.export.model import (
    AnswerGrid,
    Block,
    BoxedBlocks,
    Code,
    Document,
    Heading,
    HintBox,
    HouseStyle,
    Numbered,
    PageBreak,
    Paragraph,
    Section,
    TableBlock,
)
from staffroom.core.export.pdf import write_pdf
from staffroom.core.export.text import to_text

FORMATS = ("docx", "pdf")

__all__ = [
    "DATE_ENV",
    "FORMATS",
    "AnswerGrid",
    "Block",
    "BoxedBlocks",
    "Code",
    "Document",
    "Heading",
    "HintBox",
    "HouseStyle",
    "Numbered",
    "PageBreak",
    "Paragraph",
    "Section",
    "TableBlock",
    "export",
    "house_style_from",
    "render",
    "sheet_date",
    "to_text",
    "write_docx",
    "write_pdf",
]


def house_style_from(config: object) -> HouseStyle:
    """The teacher's house style from a Config (duck-typed to keep export
    free of a config import)."""
    general = getattr(config, "general", None)
    return HouseStyle(
        header=str(getattr(general, "house_header", "") or ""),
        footer=str(getattr(general, "house_footer", "") or ""),
    )


def render(doc: Document, path: Path) -> Path:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return write_docx(doc, path)
    if suffix == ".pdf":
        return write_pdf(doc, path)
    if suffix in (".txt", ".md"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(to_text(doc), encoding="utf-8")
        return path
    msg = f"unsupported export format {suffix!r}; use .docx, .pdf or .txt"
    raise ValueError(msg)


def export(
    doc: Document,
    out_dir: Path,
    stem: str,
    formats: Sequence[str] = FORMATS,
    *,
    split_key: bool = True,
    style: HouseStyle | None = None,
) -> list[Path]:
    """Write ``<stem>.<fmt>`` and, when the document has answer sections,
    ``<stem>_key.<fmt>`` for each format. Returns the paths written.
    ``style`` (header prefix, footer text) overrides the document's own."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if style is not None:
        doc.style = style
    written: list[Path] = []
    sheet, key = (doc.sheet(), doc.key()) if split_key else (doc, None)
    for fmt in formats:
        written.append(render(sheet, out_dir / f"{stem}.{fmt}"))
        if key is not None and key.sections:
            written.append(render(key, out_dir / f"{stem}_key.{fmt}"))
    return written
