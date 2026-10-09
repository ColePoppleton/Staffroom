"""A small Python syntax highlighter for the Library preview and the code
views of the tool panels."""

from __future__ import annotations

import builtins
import keyword
import re
from dataclasses import dataclass

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument

from staffroom.shell.theme import Palette


def _fmt(color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.DemiBold)
    if italic:
        f.setFontItalic(True)
    return f


@dataclass(frozen=True)
class CodeColors:
    """The highlighter's colours, as ``#rrggbb`` strings."""

    keyword: str
    builtin: str
    name: str
    number: str
    string: str
    comment: str

    @classmethod
    def from_palette(cls, p: Palette) -> CodeColors:
        return cls(
            p.accent, p.code_builtin, p.code_name, p.code_number, p.code_string, p.text_faint
        )


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument, colors: Palette | CodeColors) -> None:
        super().__init__(document)
        self._build(colors if isinstance(colors, CodeColors) else CodeColors.from_palette(colors))

    def set_colors(self, colors: CodeColors) -> None:
        """Re-colour (a theme change) and redraw."""
        self._build(colors)
        self.rehighlight()

    def _build(self, p: CodeColors) -> None:
        kw = "|".join(re.escape(k) for k in keyword.kwlist)
        bi = "|".join(re.escape(b) for b in dir(builtins) if not b.startswith("_"))
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = [
            (QRegularExpression(rf"\b({kw})\b"), _fmt(p.keyword, bold=True)),
            (QRegularExpression(rf"\b({bi})\b(?=\()"), _fmt(p.builtin)),
            (QRegularExpression(r"\b(def|class)\s+(\w+)"), _fmt(p.name, bold=True)),
            (QRegularExpression(r"\b\d+(\.\d+)?\b"), _fmt(p.number)),
            (QRegularExpression(r"@\w+"), _fmt(p.builtin)),
            (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), _fmt(p.string)),
            (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), _fmt(p.string)),
            (QRegularExpression(r"#[^\n]*"), _fmt(p.comment, italic=True)),
            # OCR ERL comments; no Python line starts with // (floor division).
            (QRegularExpression(r"^\s*//[^\n]*"), _fmt(p.comment, italic=True)),
        ]
        self.triple = [
            (QRegularExpression("'''"), 1),
            (QRegularExpression('"""'), 2),
        ]
        self.string_fmt = _fmt(p.string)

    def highlightBlock(self, text: str) -> None:  # noqa: N802
        for rx, fmt in self.rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next()
                group = 2 if rx.pattern().startswith(r"\b(def|class)") else 0
                self.setFormat(m.capturedStart(group), m.capturedLength(group), fmt)
        self._multiline(text)

    def _multiline(self, text: str) -> None:
        self.setCurrentBlockState(0)
        start = 0
        state = self.previousBlockState()
        if state <= 0:
            # Find the earliest opening triple quote.
            best = -1
            for rx, s in self.triple:
                m = rx.match(text)
                if m.hasMatch() and (best == -1 or m.capturedStart() < best):
                    best, state = m.capturedStart(), s
            if best == -1:
                return
            start = best
        rx = self.triple[state - 1][0]
        end = rx.match(text, start + 3 if self.previousBlockState() <= 0 else 0)
        if end.hasMatch():
            length = end.capturedEnd() - start
            self.setFormat(start, length, self.string_fmt)
            self.setCurrentBlockState(0)
            rest = text[end.capturedEnd() :]
            if rest.strip():
                pass  # good enough: one docstring per block edge
        else:
            self.setFormat(start, len(text) - start, self.string_fmt)
            self.setCurrentBlockState(state)
