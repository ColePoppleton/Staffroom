"""PDF renderer (reportlab platypus) in the house style."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import (
    PageBreak as PlatypusPageBreak,
)
from reportlab.platypus import (
    Paragraph as PlatypusParagraph,
)

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

MUTED = colors.HexColor("#667085")
ACCENT = colors.HexColor("#3B5BDB")
RULE = colors.HexColor("#C9CED9")
SOFT = colors.HexColor("#E8EDFF")
MARGIN = 18 * mm


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "tt-body", parent=base["BodyText"], fontName="Helvetica", fontSize=10.5, leading=14
    )
    return {
        "title": ParagraphStyle(
            "tt-title",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=23,
            spaceAfter=2,
        ),
        "meta": ParagraphStyle(
            "tt-meta", parent=body, textColor=MUTED, fontSize=9.5, spaceAfter=10
        ),
        "h1": ParagraphStyle(
            "tt-h1",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "tt-h2",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "body": body,
        "muted": ParagraphStyle("tt-muted", parent=body, textColor=MUTED),
        "instruction": ParagraphStyle("tt-instr", parent=body, fontName="Helvetica-Oblique"),
        "item": ParagraphStyle(
            "tt-item", parent=body, leftIndent=18, firstLineIndent=-18, spaceAfter=3
        ),
        "code": ParagraphStyle(
            "tt-code", parent=body, fontName="Courier", fontSize=9.5, leading=12, leftIndent=10
        ),
        "caption": ParagraphStyle("tt-cap", parent=body, textColor=MUTED, fontSize=8.5),
        "cell": ParagraphStyle("tt-cell", parent=body, fontSize=9.5, leading=12),
        "cellmono": ParagraphStyle(
            "tt-cellmono", parent=body, fontName="Courier", fontSize=9.5, leading=12
        ),
        "rule": ParagraphStyle(
            "tt-rule", parent=body, textColor=RULE, leftIndent=18, alignment=TA_LEFT
        ),
    }


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_pdf(doc: Document, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    st = _styles()
    header_text = doc.header_text
    footer_text = doc.footer_text

    def decorate(canvas: Any, _doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 8.5)
        canvas.setFillColor(MUTED)
        width, height = A4
        canvas.drawString(MARGIN, height - 12 * mm, header_text)
        canvas.setStrokeColor(RULE)
        canvas.line(MARGIN, height - 14 * mm, width - MARGIN, height - 14 * mm)
        page = f"Page {canvas.getPageNumber()}"
        canvas.drawCentredString(
            width / 2, 10 * mm, f"{footer_text}   ·   {page}" if footer_text else page
        )
        canvas.restoreState()

    template = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title=doc.title,
        subject=doc.topic,
    )
    story: list[Any] = [PlatypusParagraph(_esc(doc.title), st["title"])]
    meta = "   ·   ".join(x for x in (doc.topic, doc.date_text, doc.subtitle) if x)
    if meta:
        story.append(PlatypusParagraph(_esc(meta), st["meta"]))
    for section in doc.sections:
        if section.title:
            story.append(PlatypusParagraph(_esc(section.title), st["h1"]))
        for block in section.blocks:
            story += _render(block, st)
    template.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return path


def _render(block: object, st: dict[str, ParagraphStyle]) -> list[Any]:
    if isinstance(block, Heading):
        return [PlatypusParagraph(_esc(block.text), st["h1" if block.level <= 1 else "h2"])]
    if isinstance(block, Paragraph):
        style = st.get(block.style, st["body"])
        return [PlatypusParagraph(_esc(block.text), style), Spacer(1, 4)]
    if isinstance(block, Code):
        out: list[Any] = []
        if block.caption:
            out.append(PlatypusParagraph(_esc(block.caption), st["caption"]))
        out += [Preformatted(block.text, st["code"]), Spacer(1, 6)]
        return out
    if isinstance(block, Numbered):
        out = []
        for i, item in enumerate(block.items, block.start):
            first, *rest = item.splitlines() or [""]
            if block.code:
                body: list[Any] = [
                    PlatypusParagraph(f"<b>{i}.</b>", st["item"]),
                    Preformatted("\n".join([first, *rest]), st["code"]),
                ]
            else:
                text = f"<b>{i}.</b>&nbsp;&nbsp;{_esc(first)}"
                body = [PlatypusParagraph(text, st["item"])]
                body += [PlatypusParagraph(_esc(line), st["code"]) for line in rest]
            for _ in range(block.answer_lines):
                body.append(PlatypusParagraph("_" * 78, st["rule"]))
            body.append(Spacer(1, 4))
            out.append(KeepTogether(body))
        return out
    if isinstance(block, TableBlock):
        cell = st["cellmono"] if block.monospace else st["cell"]
        data = [[PlatypusParagraph(f"<b>{_esc(c)}</b>", st["cell"]) for c in block.columns]]
        data += [[PlatypusParagraph(_esc(v), cell) for v in row] for row in block.rows]
        table = Table(data, hAlign="LEFT", repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, 0), 0.8, RULE),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.3, RULE),
                    ("BACKGROUND", (0, 0), (-1, 0), SOFT),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return [table, Spacer(1, 8)]
    if isinstance(block, HintBox):
        inner = PlatypusParagraph(
            f'<font color="#3B5BDB"><b>{_esc(block.title)}:</b></font> {_esc(block.text)}',
            st["body"],
        )
        box = Table([[inner]], hAlign="LEFT")
        box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), SOFT),
                    ("BOX", (0, 0), (-1, -1), 0.6, ACCENT),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return [box, Spacer(1, 8)]
    if isinstance(block, PageBreak):
        return [PlatypusPageBreak()]
    return []
