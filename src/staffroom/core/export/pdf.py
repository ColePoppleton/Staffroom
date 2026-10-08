"""PDF renderer (reportlab platypus) in the house style."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
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
    AnswerGrid,
    BoxedBlocks,
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
FRAME_WIDTH = A4[0] - 2 * MARGIN  # what SimpleDocTemplate gives a flowable
CUT = (3, 3)  # dash pattern for cut lines
BOX_PAD = 5  # padding inside a cut-out box, points
LABEL_WIDTH = 9 * mm  # the number column in a cut-out box


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
        "boxnum": ParagraphStyle(
            "tt-boxnum", parent=body, fontName="Helvetica-Bold", fontSize=9.5, leading=12
        ),
        "boxcode": ParagraphStyle(
            "tt-boxcode", parent=body, fontName="Courier", fontSize=9.5, leading=12
        ),
        "gridhead": ParagraphStyle(
            "tt-gridhead",
            parent=body,
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
            textColor=MUTED,
            alignment=TA_CENTER,
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
    if isinstance(block, BoxedBlocks):
        return _boxed(block, st)
    if isinstance(block, AnswerGrid):
        return _answer_grid(block, st)
    if isinstance(block, PageBreak):
        return [PlatypusPageBreak()]
    return []


def box_columns(block: BoxedBlocks, st: dict[str, ParagraphStyle] | None = None) -> int:
    """How many columns the boxes can use on A4: the longest line must sit
    beside its number without wrapping, so a wide program drops to fewer
    columns (down to one) rather than spilling out of its box."""
    st = st or _styles()
    style = st["boxcode"] if block.code else st["cell"]
    longest = 0.0
    for item in block.items:
        for line in item.splitlines() or [""]:
            longest = max(longest, pdfmetrics.stringWidth(line, style.fontName, style.fontSize))
    needed = longest + LABEL_WIDTH + 2 * BOX_PAD + 4
    return max(1, min(block.columns, int(FRAME_WIDTH // needed)))


def _boxed(block: BoxedBlocks, st: dict[str, ParagraphStyle]) -> list[Any]:
    if not block.items:
        return []
    columns = box_columns(block, st)
    col_w = FRAME_WIDTH / columns
    body_style = st["boxcode"] if block.code else st["cell"]
    no_padding = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]
    cells: list[Any] = []
    for i, item in enumerate(block.items, block.start):
        label = PlatypusParagraph(f"<b>{i}</b>", st["boxnum"])
        body = (
            Preformatted(item, body_style)
            if block.code
            else PlatypusParagraph(_esc(item), body_style)
        )
        inner = Table([[label, body]], colWidths=[LABEL_WIDTH, col_w - LABEL_WIDTH - 2 * BOX_PAD])
        inner.setStyle(TableStyle(no_padding))
        cells.append(inner)
    rows = [cells[i : i + columns] for i in range(0, len(cells), columns)]
    rows[-1] += [""] * (columns - len(rows[-1]))  # trailing empty cells get no box
    grid = Table(rows, colWidths=[col_w] * columns, hAlign="LEFT")
    commands: list[Any] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), BOX_PAD),
        ("RIGHTPADDING", (0, 0), (-1, -1), BOX_PAD),
        ("TOPPADDING", (0, 0), (-1, -1), BOX_PAD),
        ("BOTTOMPADDING", (0, 0), (-1, -1), BOX_PAD),
    ]
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if cell != "":
                commands.append(("BOX", (c, r), (c, r), 0.7, MUTED, None, CUT))
    grid.setStyle(TableStyle(commands))
    return [grid, Spacer(1, 8)]


def _answer_grid(block: AnswerGrid, st: dict[str, ParagraphStyle]) -> list[Any]:
    if block.count <= 0:
        return []
    per_row = max(1, block.per_row)
    positions = list(range(block.start, block.start + block.count))
    cell_w = min(FRAME_WIDTH / per_row, 22 * mm)
    out: list[Any] = []
    for i in range(0, len(positions), per_row):
        chunk = positions[i : i + per_row]
        head = [PlatypusParagraph(str(p), st["gridhead"]) for p in chunk]
        table = Table(
            [head, [""] * len(chunk)],
            colWidths=[cell_w] * len(chunk),
            rowHeights=[None, 11 * mm],
            hAlign="LEFT",
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.6, MUTED),
                    ("BACKGROUND", (0, 0), (-1, 0), SOFT),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, 0), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 2),
                ]
            )
        )
        out += [table, Spacer(1, 6)]
    return out
