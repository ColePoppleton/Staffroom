"""Pure logic for Parsons problems: split code into blocks, shuffle with a
seed, invent distractors, and put it all back together for the key."""

from __future__ import annotations

import ast
import io
import random
import re
import tokenize
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
            "help": "Statements: a compound header with its body; Lines: every line",
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
    kind: str = ""  # a distractor's mistake, e.g. "missing colon" (the key prints it)

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
# Every distractor must be wrong in a way the sheet itself shows (#19): a syntax
# slip, a flipped comparison operator, or an off-by-one where a pupil can reason
# about the bound. Data (list literals, an assignment's starting value, a pass
# mark in an ``if``) is never changed: nothing on the sheet says what it should be.
KINDS = (
    "missing colon",
    "wrong comparison",
    "off by one in range()",
    "off by one in an index",
    "off by one in a loop condition",
)
_MUTATIONS: list[tuple[str, re.Pattern[str], str]] = [
    ("comparison", re.compile(r"(?<![<>=!])<=(?!=)"), "<"),
    ("comparison", re.compile(r"(?<![<>=!])<(?![<=])"), "<="),
    ("comparison", re.compile(r"(?<![<>=!])>=(?!=)"), ">"),
    ("comparison", re.compile(r"(?<![<>=!])>(?![>=])"), ">="),
    ("comparison", re.compile(r"(?<![<>=!])==(?!=)"), "!="),
    ("comparison", re.compile(r"!="), "=="),
]
_INT = re.compile(r"(?<![\w.])(\d+)(?![\w.])")
_COMPARISONS = {"<", "<=", ">", ">=", "==", "!="}
_CONTAINERS = (ast.List, ast.Tuple, ast.Set, ast.Dict)


def mutate(line: str, rng: random.Random) -> tuple[str, str] | None:
    """Return ``(mutated_line, kind)`` or None if nothing sensible applies.

    ``kind`` is one of :data:`KINDS`. The random draws are the same for every
    line with the same integers, so a program none of whose candidates changed
    keeps its sheet for a seed."""
    candidates: list[tuple[str, str]] = []
    stripped = line.rstrip()
    if stripped.endswith(":") and not stripped.lstrip().startswith("#"):
        candidates.append((stripped[:-1], "missing colon"))
    operators = _comparison_columns(stripped)
    for kind, pattern, replacement in _MUTATIONS:
        match = pattern.search(stripped)
        if match and match.start() in operators:
            candidates.append((pattern.sub(replacement, stripped, count=1), f"wrong {kind}"))
    bounds = _bound_ints(stripped)
    for m in _INT.finditer(stripped):
        delta = rng.choice([-1, 1])  # drawn for every integer, used or not
        if m.start(1) not in bounds:
            continue
        where, degenerate = bounds[m.start(1)]
        n = int(m.group(1))
        if n + delta >= 0 and n + delta in degenerate:  # never "+ 0", "* 1", "x[-0]"
            delta = -delta
        if n + delta >= 0 and n + delta not in degenerate:
            new = stripped[: m.start(1)] + str(n + delta) + stripped[m.end(1) :]
            candidates.append((new, f"off by one in {where}"))
    candidates = [c for c in candidates if c[0] != stripped]
    if not candidates:
        return None
    return rng.choice(candidates)


def _comparison_columns(line: str) -> set[int]:
    """Columns where a real comparison operator starts (not inside a string)."""
    found: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(line).readline):
            if tok.type == tokenize.OP and tok.string in _COMPARISONS:
                found.add(tok.start[1])
    except (tokenize.TokenError, SyntaxError):
        pass  # the first line of a longer statement: keep what was read
    return found


def _bound_ints(line: str) -> dict[int, tuple[str, set[int]]]:
    """Columns of the integers a pupil can reason about, with where each sits
    (``range()``, ``an index``, ``a loop condition``) and the values that would
    make its operation do nothing (0 beside ``+``/``-``, 0 or 1 beside ``*``).
    Integers inside list/tuple/set/dict literals, in an assignment's value, in
    strings or in an ``if`` condition are left out: they are data."""
    body = line.lstrip()
    lead = len(line) - len(body)
    parsed = _parse_line(body)
    if parsed is None:
        return {}
    tree, lineno, text = parsed
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    encoded = text.encode()
    bounds: dict[int, tuple[str, set[int]]] = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Constant)
            and type(node.value) is int
            and node.lineno == lineno
            and node.end_lineno == lineno
        ):
            continue
        where = _bound_context(node, parents)
        if where is None:
            continue
        column = len(encoded[: node.col_offset].decode())
        bounds[lead + column] = (where, _degenerate(node, parents))
    return bounds


def _parse_line(body: str) -> tuple[ast.Module, int, str] | None:
    """Parse one line on its own; a compound header gets a body to parse.
    Returns the tree, the line the original sits on, and that line's text."""
    attempts = [(body, 1, body)]
    if body.endswith(":"):
        head = re.sub(r"^elif\b", "if  ", body)  # same width, so columns hold
        attempts.append((head + "\n    pass", 1, head))
        attempts.append(("try:\n    pass\n" + body + "\n    pass", 3, body))
    for source, lineno, text in attempts:
        try:
            return ast.parse(source), lineno, text
        except SyntaxError:
            continue
    return None


def _bound_context(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str | None:
    in_comparison = False
    while node in parents:
        parent = parents[node]
        if isinstance(parent, _CONTAINERS):
            return None
        if (
            isinstance(parent, ast.Call)
            and node in parent.args
            and isinstance(parent.func, ast.Name)
            and parent.func.id == "range"
        ):
            return "range()"
        if isinstance(parent, ast.Subscript) and node is parent.slice:
            return "an index"
        if isinstance(parent, ast.Compare):
            in_comparison = True
        if isinstance(parent, ast.While) and node is parent.test:
            return "a loop condition" if in_comparison else None
        if isinstance(parent, ast.stmt):
            return None
        node = parent
    return None


def _degenerate(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> set[int]:
    parent = parents.get(node)
    if isinstance(parent, ast.BinOp):
        if isinstance(parent.op, ast.Add | ast.Sub):
            return {0}
        return {0, 1}
    if isinstance(parent, ast.UnaryOp):
        return {0}
    return set()


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
        made.append(Block(text, block.indent, -1, distractor=True, kind=result[1]))
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
