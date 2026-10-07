"""The house style: one document model rendered to docx, PDF or plain text.

Every worksheet, key and report in the project goes through here so they all
look the same: a header with title, topic and date; a footer with page
numbers; monospace blocks for code; answer sections that split off into a
separate key file.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from teaching_tools.core.export.docx import write_docx
from teaching_tools.core.export.model import (
    Block,
    Code,
    Document,
    Heading,
    HintBox,
    Numbered,
    PageBreak,
    Paragraph,
    Section,
    TableBlock,
)
from teaching_tools.core.export.pdf import write_pdf
from teaching_tools.core.export.text import to_text

FORMATS = ("docx", "pdf")

__all__ = [
    "FORMATS",
    "Block",
    "Code",
    "Document",
    "Heading",
    "HintBox",
    "Numbered",
    "PageBreak",
    "Paragraph",
    "Section",
    "TableBlock",
    "export",
    "render",
    "to_text",
    "write_docx",
    "write_pdf",
]


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
) -> list[Path]:
    """Write ``<stem>.<fmt>`` and, when the document has answer sections,
    ``<stem>_key.<fmt>`` for each format. Returns the paths written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    sheet, key = (doc.sheet(), doc.key()) if split_key else (doc, None)
    for fmt in formats:
        written.append(render(sheet, out_dir / f"{stem}.{fmt}"))
        if key is not None and key.sections:
            written.append(render(key, out_dir / f"{stem}_key.{fmt}"))
    return written
