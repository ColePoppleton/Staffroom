"""Pure entry point: translate text between Python, OCR ERL and AQA."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Literal

from staffroom.tools.pseudocode import ir
from staffroom.tools.pseudocode.emit import Dialect, emit
from staffroom.tools.pseudocode.from_python import from_python
from staffroom.tools.pseudocode.pseudo_parser import parse_pseudo

Language = Literal["python", "ocr", "aqa"]
LANGUAGES: tuple[Language, ...] = ("python", "ocr", "aqa")
LANGUAGE_LABELS: dict[str, str] = {
    "python": "Python",
    "ocr": "OCR Exam Reference Language",
    "aqa": "AQA pseudocode",
}
Source = Literal["guess", "python", "ocr", "aqa"]
Target = Literal["ocr", "aqa", "python"]


@dataclass
class Options:
    source: Source = field(
        default="guess",
        metadata={
            "label": "From",
            "help": "guess: work the language out from the code itself, then the file name",
        },
    )
    target: Target = field(default="ocr", metadata={"label": "To"})
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


# -- guessing the source language -------------------------------------------
# Tokens that only one of the three languages writes. Case matters: AQA
# shouts its keywords, OCR ERL whispers them, Python has its own words.
_PYTHON_WORDS = frozenset(
    {"def", "elif", "import", "None", "True", "False", "range", "append", "len", "lambda", "class"}
)
_OCR_WORDS = frozenset(
    {
        "endif",
        "endwhile",
        "endprocedure",
        "endfunction",
        "endswitch",
        "elseif",
        "procedure",
        "function",
        "next",
        "then",
        "until",
        "do",
        "to",
        "array",
        "switch",
        "case",
        "length",
        "substring",
        "openRead",
        "openWrite",
        "readLine",
        "writeLine",
        "endOfFile",
    }
)
_AQA_WORDS = frozenset(
    {
        "OUTPUT",
        "USERINPUT",
        "SUBROUTINE",
        "ENDSUBROUTINE",
        "IF",
        "THEN",
        "ELSE",
        "ENDIF",
        "WHILE",
        "ENDWHILE",
        "FOR",
        "TO",
        "STEP",
        "IN",
        "ENDFOR",
        "REPEAT",
        "UNTIL",
        "RETURN",
        "CONSTANT",
        "LEN",
        "SUBSTRING",
        "POSITION",
        "STRING_TO_INT",
        "STRING_TO_REAL",
        "INT_TO_STRING",
        "REAL_TO_STRING",
        "RANDOM_INT",
        "CHAR_TO_CODE",
        "CODE_TO_CHAR",
    }
)
_WORD = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
_STRING = re.compile(
    r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\''
)
_PYTHON_BLOCK = re.compile(r"^\s*(if|elif|else|for|while|def|class|try|except|finally|with)\b.*:$")


def _strip_literals(text: str) -> str:
    """Drop string literals and comment lines: a worksheet that *prints* the
    word ``endif`` is not written in OCR ERL."""
    lines = [line for line in text.splitlines() if not line.lstrip().startswith(("#", "//"))]
    return _STRING.sub('""', "\n".join(lines))


def dialect_scores(text: str) -> dict[Language, int]:
    """How many distinctive tokens of each language the text uses."""
    code = _strip_literals(text)
    words = _WORD.findall(code)
    scores: dict[Language, int] = {
        "python": sum(w in _PYTHON_WORDS for w in words),
        "ocr": sum(w in _OCR_WORDS for w in words),
        "aqa": sum(w in _AQA_WORDS for w in words) + code.count("←"),
    }
    scores["python"] += sum(bool(_PYTHON_BLOCK.match(line)) for line in code.splitlines())
    return scores


def guess_dialect(text: str) -> Language | None:
    """The language the text is most likely written in, or ``None`` when it is
    genuinely ambiguous (no distinctive token, or a tie)."""
    scores = dialect_scores(text)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best, runner_up = ranked[0], ranked[1]
    if best[1] == 0 or best[1] == runner_up[1]:
        return None
    return best[0]


def dialect_from_name(name: str) -> Language | None:
    """What a file name says about its language: ``.py`` is Python, ``.aqa``
    or ``.ocr`` anywhere in the name names that board. Otherwise ``None``."""
    lower = name.lower()
    if lower.endswith(".py"):
        return "python"
    if ".aqa" in lower:
        return "aqa"
    if ".ocr" in lower:
        return "ocr"
    return None


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
