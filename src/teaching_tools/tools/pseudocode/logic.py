"""Pure entry point: translate text between Python, OCR ERL and AQA."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Literal

from teaching_tools.tools.pseudocode import ir
from teaching_tools.tools.pseudocode.emit import Dialect, emit
from teaching_tools.tools.pseudocode.from_python import from_python
from teaching_tools.tools.pseudocode.pseudo_parser import parse_pseudo

Language = Literal["python", "ocr", "aqa"]
LANGUAGE_LABELS: dict[str, str] = {
    "python": "Python",
    "ocr": "OCR Exam Reference Language",
    "aqa": "AQA pseudocode",
}
Direction = Literal[
    "python_to_ocr",
    "python_to_aqa",
    "ocr_to_python",
    "aqa_to_python",
    "ocr_to_aqa",
    "aqa_to_ocr",
]


@dataclass
class Options:
    direction: Direction = field(default="python_to_ocr", metadata={"label": "Direction"})
    formats: Literal["txt", "none"] = field(
        default="txt",
        metadata={"label": "Save output", "help": "txt: write the translation to a file"},
    )


@dataclass
class Translation:
    text: str
    source: Language
    target: Language
    dropped: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.dropped

    def report(self) -> str:
        lines: list[str] = []
        if self.dropped:
            lines.append("Could not translate:")
            lines += [f"  - {d}" for d in self.dropped]
        else:
            lines.append("Everything translated.")
        if self.notes:
            lines.append("Notes:")
            lines += [f"  - {n}" for n in self.notes]
        return "\n".join(lines)


def split_direction(direction: str) -> tuple[Language, Language]:
    src, _, dst = direction.partition("_to_")
    if src not in LANGUAGE_LABELS or dst not in LANGUAGE_LABELS or src == dst:
        msg = f"unknown direction {direction!r}"
        raise ValueError(msg)
    return src, dst  # type: ignore[return-value]


def to_ir(text: str, source: Language) -> tuple[ir.Program, list[str], list[str]]:
    if source == "python":
        program, report = from_python(text)
        return program, report.dropped, report.notes
    program, preport = parse_pseudo(text, source)
    return program, preport.dropped, preport.notes


def translate(text: str, source: Language, target: Language) -> Translation:
    program, dropped, notes = to_ir(text, source)
    out, ereport = emit(program, target)
    all_notes: list[str] = []
    for n in [*notes, *ereport.notes]:
        if n not in all_notes:
            all_notes.append(n)
    return Translation(out, source, target, dropped, all_notes)


def translate_direction(text: str, direction: str) -> Translation:
    src, dst = split_direction(direction)
    return translate(text, src, dst)


class _Normalise(ast.NodeTransformer):
    """Trivial spellings that mean the same thing: ``range(n)`` is
    ``range(0, n)``, ``s[:2]`` is ``s[0:2]``, ``x += 1`` is ``x = x + 1``."""

    def visit_Slice(self, node: ast.Slice) -> ast.AST:
        self.generic_visit(node)
        if node.lower is None:
            node.lower = ast.Constant(0)
        return node

    def visit_AugAssign(self, node: ast.AugAssign) -> ast.AST:
        self.generic_visit(node)
        load: ast.expr = node.target
        if isinstance(node.target, ast.Name):
            load = ast.Name(node.target.id, ast.Load())
        return ast.Assign([node.target], ast.BinOp(load, node.op, node.value))

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.func, ast.Name) and node.func.id == "range" and len(node.args) == 1:
            node.args.insert(0, ast.Constant(0))
        return node


def normalised_dump(source: str) -> str:
    """``ast.dump`` after normalising, for equivalence checks."""
    tree = _Normalise().visit(ast.parse(source))
    return ast.dump(tree)


def same_program(a: str, b: str) -> bool:
    return normalised_dump(a) == normalised_dump(b)


def extension_for(language: Language) -> str:
    return {"python": ".py", "ocr": ".ocr.txt", "aqa": ".aqa.txt"}[language]


def emit_dialect(program: ir.Program, dialect: Dialect) -> str:
    return emit(program, dialect)[0]
