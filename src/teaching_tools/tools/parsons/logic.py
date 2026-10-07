"""Pure logic for Parsons problems: split code into blocks, shuffle with a
seed, invent distractors, and put it all back together for the key."""

from __future__ import annotations

import ast
import random
import re
from dataclasses import dataclass, field
from typing import Literal

Granularity = Literal["statement", "line"]


@dataclass
class Options:
    seed: int = field(default=1, metadata={"label": "Seed", "min": 0, "max": 999_999})
    distractors: int = field(default=2, metadata={"label": "Distractors", "min": 0, "max": 10})
    granularity: Granularity = field(
        default="statement",
        metadata={
            "label": "Split at",
            "help": "statement: compound headers and bodies; line: every line",
        },
    )
    show_indentation: bool = field(
        default=True,
        metadata={"label": "Show indentation", "help": "Off: pupils must work out the indents too"},
    )
    hint: bool = field(default=True, metadata={"label": "Include a hint box"})
    formats: Literal["both", "docx", "pdf"] = field(default="both", metadata={"label": "Output"})


@dataclass(frozen=True)
class Block:
    text: str  # dedented to its own indent level
    indent: int  # levels of 4 spaces
    order: int  # position in the solution, 0-based
    distractor: bool = False

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()


@dataclass
class Problem:
    source: str
    solution: list[Block]  # in correct order
    shuffled: list[Block]  # as printed, including distractors
    seed: int
    granularity: Granularity

    def numbered(self) -> list[tuple[int, Block]]:
        return list(enumerate(self.shuffled, 1))

    def answer_order(self) -> list[int]:
        """Printed numbers (1-based) of the real blocks in solution order."""
        position = {id(b): i for i, b in enumerate(self.shuffled, 1)}
        return [position[id(b)] for b in self.solution]

    def distractor_numbers(self) -> list[int]:
        return [i for i, b in enumerate(self.shuffled, 1) if b.distractor]


# ---------------------------------------------------------------- splitting
def normalise(source: str) -> str:
    """Tabs to four spaces, trailing whitespace off, ending newline."""
    lines = [ln.replace("\t", "    ").rstrip() for ln in source.splitlines()]
    return "\n".join(lines).rstrip("\n") + "\n"


def _indent_of(line: str) -> int:
    return (len(line) - len(line.lstrip(" "))) // 4


def split_lines(source: str) -> list[Block]:
    """One block per non-blank, non-comment line."""
    blocks: list[Block] = []
    for line in normalise(source).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        blocks.append(Block(line.strip(), _indent_of(line), len(blocks)))
    return blocks


def split_statements(source: str) -> list[Block]:
    """One block per statement: a compound statement's header line is a
    block and each statement in its body is a block of its own, so the pupil
    rebuilds structure as well as order. Comment-only lines are dropped
    (``ast`` does not keep them)."""
    text = normalise(source)
    tree = ast.parse(text)
    lines = text.splitlines()
    spans: list[tuple[int, int]] = []  # 1-based inclusive line spans

    def visit(statements: list[ast.stmt]) -> None:
        for node in statements:
            bodies = _bodies(node)
            if bodies:
                first_body_line = min(b[0].lineno for b in bodies if b)
                spans.append((node.lineno, first_body_line - 1))
                for body in bodies:
                    visit(body)
                _else_headers(node, spans, lines)
            else:
                spans.append((node.lineno, node.end_lineno or node.lineno))

    visit(tree.body)
    spans.sort()
    blocks: list[Block] = []
    for start, end in spans:
        chunk = [
            ln for ln in lines[start - 1 : end] if ln.strip() and not ln.lstrip().startswith("#")
        ]
        if not chunk:
            continue
        indent = _indent_of(chunk[0])
        dedented = "\n".join(
            ln[indent * 4 :] if ln.startswith(" " * indent * 4) else ln.lstrip() for ln in chunk
        )
        blocks.append(Block(dedented, indent, len(blocks)))
    return blocks


def _bodies(node: ast.stmt) -> list[list[ast.stmt]]:
    bodies: list[list[ast.stmt]] = []
    for attr in ("body", "orelse", "finalbody"):
        value = getattr(node, attr, None)
        if isinstance(value, list) and value and all(isinstance(v, ast.stmt) for v in value):
            bodies.append(value)
    for handler in getattr(node, "handlers", []) or []:
        if isinstance(handler, ast.ExceptHandler):
            bodies.append(handler.body)
    return bodies


def _else_headers(node: ast.stmt, spans: list[tuple[int, int]], lines: list[str]) -> None:
    """``else:``/``elif``/``except``/``finally`` header lines are blocks too."""
    for attr in ("orelse", "finalbody"):
        body = getattr(node, attr, None)
        if isinstance(body, list) and body and isinstance(body[0], ast.stmt):
            header_line = body[0].lineno - 1
            text = lines[header_line - 1].strip() if header_line >= 1 else ""
            if text.startswith(("else", "elif", "finally")) and text.endswith(":"):
                spans.append((header_line, header_line))
            elif isinstance(node, ast.If) and isinstance(body[0], ast.If) and text == "":
                pass
    for handler in getattr(node, "handlers", []) or []:
        if isinstance(handler, ast.ExceptHandler):
            first = handler.body[0].lineno
            spans.append((handler.lineno, first - 1))


def split(source: str, granularity: Granularity = "statement") -> list[Block]:
    return split_lines(source) if granularity == "line" else split_statements(source)


# ---------------------------------------------------------------- distractors
_MUTATIONS: list[tuple[str, re.Pattern[str], str]] = [
    ("comparison", re.compile(r"(?<![<>=!])<=(?!=)"), "<"),
    ("comparison", re.compile(r"(?<![<>=!])<(?![<=])"), "<="),
    ("comparison", re.compile(r"(?<![<>=!])>=(?!=)"), ">"),
    ("comparison", re.compile(r"(?<![<>=!])>(?![>=])"), ">="),
    ("comparison", re.compile(r"(?<![<>=!])==(?!=)"), "!="),
    ("comparison", re.compile(r"!="), "=="),
]
_INT = re.compile(r"(?<![\w.])(\d+)(?![\w.])")


def mutate(line: str, rng: random.Random) -> tuple[str, str] | None:
    """Return ``(mutated_line, kind)`` or None if nothing sensible applies."""
    candidates: list[tuple[str, str]] = []
    stripped = line.rstrip()
    if stripped.endswith(":") and not stripped.lstrip().startswith("#"):
        candidates.append((stripped[:-1], "missing colon"))
    for kind, pattern, replacement in _MUTATIONS:
        if pattern.search(stripped):
            candidates.append((pattern.sub(replacement, stripped, count=1), f"wrong {kind}"))
    for m in _INT.finditer(stripped):
        n = int(m.group(1))
        delta = rng.choice([-1, 1])
        if n + delta >= 0:
            new = stripped[: m.start(1)] + str(n + delta) + stripped[m.end(1) :]
            candidates.append((new, "off by one"))
    candidates = [c for c in candidates if c[0] != stripped]
    if not candidates:
        return None
    return rng.choice(candidates)


def make_distractors(blocks: list[Block], count: int, rng: random.Random) -> list[Block]:
    """Mutate the first line of ``count`` distinct blocks. Never produces a
    duplicate of a real block."""
    real = {b.text for b in blocks}
    made: list[Block] = []
    seen: set[str] = set()
    order = list(blocks)
    rng.shuffle(order)
    for _attempt in range(count * 6):
        if len(made) >= count or not order:
            break
        block = order[_attempt % len(order)]
        first, *rest = block.lines
        result = mutate(first, rng)
        if result is None:
            continue
        text = "\n".join([result[0], *rest])
        if text in real or text in seen:
            continue
        seen.add(text)
        made.append(Block(text, block.indent, -1, distractor=True))
    return made


# ---------------------------------------------------------------- the problem
def make_problem(source: str, options: Options | None = None) -> Problem:
    options = options or Options()
    solution = split(source, options.granularity)
    if len(solution) < 2:
        msg = "Need at least two statements to make a Parsons problem."
        raise ValueError(msg)
    rng = random.Random(options.seed)
    distractors = make_distractors(solution, options.distractors, rng)
    shuffled = [*solution, *distractors]
    for _ in range(20):  # make sure the printed order is not the solution
        rng.shuffle(shuffled)
        if [b for b in shuffled if not b.distractor] != solution:
            break
    return Problem(
        source=normalise(source),
        solution=solution,
        shuffled=shuffled,
        seed=options.seed,
        granularity=options.granularity,
    )


def reconstruct(blocks: list[Block]) -> str:
    """Code from blocks in solution order, re-indented."""
    out: list[str] = []
    for block in blocks:
        for line in block.lines:
            out.append(" " * (4 * block.indent) + line)
    return "\n".join(out) + "\n"


def same_program(a: str, b: str) -> bool:
    """Equal ignoring blank lines, comments and trailing whitespace."""

    def strip(text: str) -> list[str]:
        return [
            ln.rstrip()
            for ln in normalise(text).splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")
        ]

    try:
        return ast.dump(ast.parse(a)) == ast.dump(ast.parse(b)) and strip(a) == strip(b)
    except SyntaxError:
        return False


def render_block(block: Block, show_indentation: bool) -> str:
    pad = "    " * block.indent if show_indentation else ""
    return "\n".join(pad + ln for ln in block.lines)
