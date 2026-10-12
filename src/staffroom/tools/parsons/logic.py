"""Pure logic for Parsons problems: split code into blocks, shuffle with a
seed, invent distractors, and put it all back together for the key."""

from __future__ import annotations

import ast
import random
import re
import tokenize
from collections.abc import Sequence
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
    line: int = 0  # where its first line sits in the normalised program (1-based)
    original: str = ""  # a distractor's real first line, before the mistake

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
    for number, line in enumerate(normalise(source).splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        blocks.append(Block(line.strip(), _indent_of(line), len(blocks), line=number))
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
        numbered = [
            (n, ln)
            for n, ln in enumerate(lines[start - 1 : end], start)
            if ln.strip() and not ln.lstrip().startswith("#")
        ]
        if not numbered:
            continue
        chunk = [ln for _n, ln in numbered]
        indent = _indent_of(chunk[0])
        dedented = "\n".join(
            ln[indent * 4 :] if ln.startswith(" " * indent * 4) else ln.lstrip() for ln in chunk
        )
        blocks.append(Block(dedented, indent, len(blocks), line=numbered[0][0]))
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
# slip, a flipped comparison operator, an off-by-one where a pupil can reason
# about the bound, or a variable swapped for another the program has already
# set up, of the same sort (#29). Data (list literals, an assignment's starting
# value, a pass mark in an ``if``, strings) is never changed: nothing on the
# sheet says what it should be.
KINDS = (
    "missing colon",
    "wrong comparison",
    "off by one in range()",
    "off by one in an index",
    "off by one in a loop condition",
    "wrong variable",
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


def mutate(line: str, rng: random.Random, swaps: Sequence[Swap] = ()) -> tuple[str, str] | None:
    """Return ``(mutated_line, kind)`` or None if nothing sensible applies.

    ``kind`` is one of :data:`KINDS`. ``swaps`` are the wrong variables this
    line can take (:func:`variable_swaps`; none for a line read on its own).
    The random draws are the same for every line with the same integers, so a
    program none of whose candidates changed keeps its sheet for a seed."""
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
    for swap in swaps:
        end = swap.column + len(swap.old)
        if stripped[swap.column : end] != swap.old:
            continue  # not this line after all
        new = stripped[: swap.column] + swap.new + stripped[end:]
        if _parse_line(new) is not None:
            candidates.append((new, "wrong variable"))
    candidates = [c for c in candidates if c[0] != stripped]
    if not candidates:
        return None
    return rng.choice(candidates)


def _comparison_columns(line: str) -> set[int]:
    """Columns where a real comparison operator starts (not inside a string)."""
    found: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(iter([line]).__next__):  # one line, no I/O
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


def make_distractors(
    blocks: list[Block],
    count: int,
    rng: random.Random,
    swaps: dict[int, list[Swap]] | None = None,
) -> list[Block]:
    """Mutate the first line of ``count`` distinct blocks. Never produces a
    duplicate of a real block. ``swaps`` maps a program line to its wrong
    variables (:func:`variable_swaps`)."""
    swaps = swaps or {}
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
        result = mutate(first, rng, swaps.get(block.line, ()))
        if result is None:
            continue
        text = "\n".join([result[0], *rest])
        if text in real or text in seen:
            continue
        seen.add(text)
        made.append(Block(text, block.indent, -1, distractor=True, kind=result[1], original=first))
    return made


# ---------------------------------------------------------------- wrong variables
# A pupil who types the wrong name types one they have just been using, of the
# same sort: ``count`` for ``score``, not the list ``scores`` for a number (the
# Bugs tool's stand-ins are the model). The stand-in must already be set when
# the line runs, in the same function or at the top level, and be the same kind
# of value as far as the program's own assignments show; a name whose kind is
# unclear (a function's parameter, a value from an unknown call) is never
# swapped, nor is a name in a list or other literal, a string, or a call's
# function. Of those, the most recently set is the one a pupil would type.
@dataclass(frozen=True)
class Swap:
    """One wrong variable for a line: ``old`` at ``column`` (in the line
    without its indent) becomes ``new``."""

    column: int
    old: str
    new: str


_NUMBER_CALLS = {"int", "float", "len", "sum", "round", "abs", "min", "max", "ord"}
_STR_CALLS = {"str", "input", "chr", "repr", "format"}
_LIST_CALLS = {"list", "sorted"}
_SCOPES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)
# Names bound in these live only inside them; names in literals are data.
_OWN_NAMES = (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_NOT_SWAPPED = (*_CONTAINERS, ast.JoinedStr, *_OWN_NAMES)


class _Names:
    """Which names each scope sets, on which lines, and of what kind."""

    def __init__(self, tree: ast.Module) -> None:
        self.tree = tree
        self.stores: dict[ast.AST, dict[str, list[int]]] = {}  # scope -> name -> lines
        self.values: dict[str, list[ast.expr]] = {}  # name -> what it was set to
        self.items: dict[str, list[ast.expr]] = {}  # loop variable -> what it loops over
        self.uses: list[tuple[ast.Name, ast.AST]] = []  # names a pupil could mistype
        self._walk(tree, tree, swappable=True)
        # Names set from other names settle in a few passes; each pass reads
        # only the one before, so the result does not depend on set order.
        self.kinds: dict[str, str] = {}
        for _ in range(10):
            settled = {name: self._name_kind(name) for name in self.values.keys() | self.items}
            if settled == self.kinds:
                break
            self.kinds = settled

    def _walk(self, node: ast.AST, scope: ast.AST, *, swappable: bool) -> None:
        for child in ast.iter_child_nodes(node):
            inner = child if isinstance(child, _SCOPES) else scope
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                args = child.args
                for a in args.posonlyargs + args.args + args.kwonlyargs:
                    self.stores.setdefault(child, {}).setdefault(a.arg, []).append(child.lineno)
            if isinstance(child, ast.Name):
                if isinstance(child.ctx, ast.Store) and swappable:
                    self.stores.setdefault(scope, {}).setdefault(child.id, []).append(child.lineno)
                elif isinstance(child.ctx, ast.Load) and swappable:
                    called = isinstance(node, ast.Call) and node.func is child
                    if not called:
                        self.uses.append((child, scope))
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        self.values.setdefault(target.id, []).append(child.value)
            elif isinstance(child, ast.AnnAssign | ast.AugAssign):
                if isinstance(child.target, ast.Name) and child.value is not None:
                    self.values.setdefault(child.target.id, []).append(child.value)
            elif isinstance(child, ast.For) and isinstance(child.target, ast.Name):
                self.items.setdefault(child.target.id, []).append(child.iter)
            self._walk(child, inner, swappable=swappable and not isinstance(child, _NOT_SWAPPED))

    def _name_kind(self, name: str) -> str:
        found = {self._kind(v) for v in self.values.get(name, [])}
        found |= {self._item_kind(it) for it in self.items.get(name, [])}
        return found.pop() if len(found) == 1 else "unknown"

    def _kind(self, value: ast.expr) -> str:
        if isinstance(value, ast.Constant):
            v = value.value
            if isinstance(v, bool):
                return "bool"
            if isinstance(v, int | float):
                return "number"
            return "str" if isinstance(v, str) else "unknown"
        if isinstance(value, ast.JoinedStr):
            return "str"
        if isinstance(value, ast.List | ast.ListComp):
            return "list"
        if isinstance(value, ast.Dict | ast.DictComp):
            return "dict"
        if isinstance(value, ast.Compare | ast.BoolOp):
            return "bool"
        if isinstance(value, ast.Name):
            return self.kinds.get(value.id, "unknown")
        if isinstance(value, ast.UnaryOp):
            return "bool" if isinstance(value.op, ast.Not) else self._kind(value.operand)
        if isinstance(value, ast.BinOp):
            left, right = self._kind(value.left), self._kind(value.right)
            if isinstance(value.op, ast.Div) and "number" in (left, right):
                return "number"
            return left if left != "unknown" else right
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            fn = value.func.id
            if fn in _NUMBER_CALLS:
                return "number"
            if fn in _STR_CALLS:
                return "str"
            if fn in _LIST_CALLS:
                return "list"
            if fn in ("bool", "dict"):
                return fn
        return "unknown"

    def _item_kind(self, iterable: ast.expr) -> str:
        """The kind of value a ``for`` loop over ``iterable`` hands out."""
        if (
            isinstance(iterable, ast.Call)
            and isinstance(iterable.func, ast.Name)
            and iterable.func.id == "range"
        ):
            return "number"
        if isinstance(iterable, ast.List | ast.Tuple | ast.Set):
            kinds = {self._kind(e) for e in iterable.elts}
            return kinds.pop() if len(kinds) == 1 else "unknown"
        if isinstance(iterable, ast.Name):
            if self.kinds.get(iterable.id) == "str":
                return "str"
            values = self.values.get(iterable.id, [])
            listed = [v for v in values if isinstance(v, ast.List)]
            if listed and len(listed) == len(values):
                kinds = {self._kind(e) for v in listed for e in v.elts}
                return kinds.pop() if len(kinds) == 1 else "unknown"
        return "unknown"

    def stand_in(self, use: ast.Name, scope: ast.AST) -> str | None:
        """The name a pupil might type instead of ``use``, or None."""
        kind = self.kinds.get(use.id, "unknown")
        if kind == "unknown":
            return None
        visible = dict(self.stores.get(self.tree, {}))
        if scope is not self.tree:
            visible.update(self.stores.get(scope, {}))
        # Set on an earlier line, so it already exists when this line runs.
        earlier = {
            name: max(n for n in at if n < use.lineno)
            for name, at in visible.items()
            if name != use.id and min(at) < use.lineno and self.kinds.get(name) == kind
        }
        # The most recently set; ties in the order the names were first set.
        return max(earlier, key=lambda name: earlier[name], default=None)


def variable_swaps(source: str) -> dict[int, list[Swap]]:
    """For each line of ``source`` (1-based), the wrong variables it can take:
    each name it reads, swapped for the one a pupil might plausibly type
    instead. Lines are as in ``source``; columns are counted without the
    line's indent. Invalid code has none."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    names = _Names(tree)
    lines = source.splitlines()
    swaps: dict[int, list[Swap]] = {}
    for use, scope in names.uses:
        if use.end_lineno != use.lineno:
            continue
        new = names.stand_in(use, scope)
        if new is None:
            continue
        line = lines[use.lineno - 1]
        lead = len(line) - len(line.lstrip())
        column = len(line.encode()[: use.col_offset].decode()) - lead
        swaps.setdefault(use.lineno, []).append(Swap(column, use.id, new))
    return swaps


# ---------------------------------------------------------------- the problem
def make_problem(source: str, options: Options | None = None) -> Problem:
    options = options or Options()
    solution = split(source, options.granularity)
    if len(solution) < 2:
        msg = "Need at least two statements to make a Parsons problem."
        raise ValueError(msg)
    rng = random.Random(options.seed)
    swaps = variable_swaps(normalise(source))
    distractors = make_distractors(solution, options.distractors, rng, swaps)
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
