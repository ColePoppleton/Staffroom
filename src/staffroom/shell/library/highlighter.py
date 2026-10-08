"""A small Python syntax highlighter for the preview pane."""

from __future__ import annotations

import builtins
import keyword
import re

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


class PythonHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument, palette: Palette) -> None:
        super().__init__(document)
        p = palette
        kw = "|".join(re.escape(k) for k in keyword.kwlist)
        bi = "|".join(re.escape(b) for b in dir(builtins) if not b.startswith("_"))
        self.rules: list[tuple[QRegularExpression, QTextCharFormat]] = [
            (QRegularExpression(rf"\b({kw})\b"), _fmt(p.accent, bold=True)),
            (QRegularExpression(rf"\b({bi})\b(?=\()"), _fmt(p.code_builtin)),
            (QRegularExpression(r"\b(def|class)\s+(\w+)"), _fmt(p.code_name, bold=True)),
            (QRegularExpression(r"\b\d+(\.\d+)?\b"), _fmt(p.code_number)),
            (QRegularExpression(r"@\w+"), _fmt(p.code_builtin)),
            (QRegularExpression(r"'[^'\\]*(\\.[^'\\]*)*'"), _fmt(p.code_string)),
            (QRegularExpression(r'"[^"\\]*(\\.[^"\\]*)*"'), _fmt(p.code_string)),
            (QRegularExpression(r"#[^\n]*"), _fmt(p.text_faint, italic=True)),
        ]
        self.triple = [
            (QRegularExpression("'''"), 1),
            (QRegularExpression('"""'), 2),
        ]
        self.string_fmt = _fmt(p.code_string)

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
