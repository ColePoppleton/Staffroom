"""Pure question generators. Each is ``(seed, count, difficulty) -> list[Question]``
and is deterministic for a seed, so a sheet can be regenerated from the
seed printed on it. Answers are checked by independent computation in the
tests (``int(x, 2)`` and friends), never by the generator's own arithmetic.
"""

from __future__ import annotations

import heapq
import random
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Literal

Difficulty = Literal["easy", "medium", "hard"]
Level = Literal["gcse", "a_level"]
Laws = Literal["absorption", "de_morgan", "identities", "all"]


@dataclass(frozen=True)
class Step:
    """One law applied in a key: ``before`` rewrites to ``after`` (via an optional
    middle form), leaving the whole expression as ``result``. Every text is in the
    question's own letters."""

    law: str
    before: str
    after: str
    result: str
    via: str = ""

    def text(self) -> str:
        chain = " = ".join(x for x in (self.before, self.via, self.after) if x)
        return f"{self.law}: {chain}, leaving {self.result}"


@dataclass(frozen=True)
class Question:
    prompt: str
    answer: str
    working: str = ""  # shown in the key
    answer_lines: int = 1
    table: tuple[tuple[str, ...], ...] | None = None  # columns + rows for the sheet
    steps: tuple[Step, ...] = ()  # the key's reasoning, structured, for the property tests


Generator = Callable[[int, int, Difficulty], list[Question]]

# A sheet of fewer than one question is empty; more than this does not fit a lesson or a
# printer tray. The panel's spin box and ``generate`` share these limits.
MIN_COUNT = 1
MAX_COUNT = 60


@dataclass
class Options:
    topic: Literal[
        "binary",
        "twos_complement",
        "binary_addition",
        "shifts",
        "truth_tables",
        "boolean_simplification",
        "file_size",
        "rle",
        "huffman",
    ] = field(default="binary", metadata={"label": "Topic"})
    count: int = field(
        default=10, metadata={"label": "Questions", "min": MIN_COUNT, "max": MAX_COUNT}
    )
    seed: int = field(default=42, metadata={"label": "Seed", "min": 0, "max": 999_999})
    difficulty: Difficulty = field(default="medium", metadata={"label": "Difficulty"})
    level: Level = field(
        default="gcse",
        metadata={
            "label": "Level",
            "help": "GCSE follows the board; A level adds XOR, and NAND/NOR at Hard",
        },
    )
    laws: Laws = field(
        default="absorption",
        metadata={
            "label": "Boolean laws",
            "help": "Identities allows X AND X, NOT NOT X and 0/1 on the sheet",
        },
    )
    formats: Literal["both", "docx", "pdf"] = field(default="both", metadata={"label": "Output"})


def _bits(difficulty: Difficulty) -> int:
    return {"easy": 4, "medium": 8, "hard": 12}[difficulty]


def bin_str(n: int, bits: int) -> str:
    return format(n, f"0{bits}b")


def grouped(b: str) -> str:
    return " ".join(b[i : i + 4] for i in range(0, len(b), 4))


# ---------------------------------------------------------------- 1. binary / denary / hex
def binary(seed: int, count: int, difficulty: Difficulty) -> list[Question]:
    rng = random.Random(seed)
    bits = _bits(difficulty)
    out: list[Question] = []
    kinds = ["d2b", "b2d"] if difficulty == "easy" else ["d2b", "b2d", "d2h", "h2d", "b2h", "h2b"]
    for _ in range(count):
        n = rng.randrange(1, 2**bits)
        kind = rng.choice(kinds)
        b, h = bin_str(n, bits), format(n, "X").rjust(bits // 4, "0")
        if kind == "d2b":
            out.append(Question(f"Convert {n} to binary ({bits} bits).", grouped(b)))
        elif kind == "b2d":
            out.append(Question(f"Convert {grouped(b)} to denary.", str(n)))
        elif kind == "d2h":
            out.append(Question(f"Convert {n} to hexadecimal.", h))
        elif kind == "h2d":
            out.append(Question(f"Convert {h} (hex) to denary.", str(n)))
        elif kind == "b2h":
            out.append(Question(f"Convert {grouped(b)} to hexadecimal.", h, "Group into nibbles."))
        else:
            out.append(
                Question(f"Convert {h} (hex) to binary.", grouped(b), "Each hex digit is a nibble.")
            )
    return out


# ---------------------------------------------------------------- 2. two's complement
def twos_complement(seed: int, count: int, difficulty: Difficulty) -> list[Question]:
    rng = random.Random(seed)
    bits = 8
    out: list[Question] = []
    for _ in range(count):
        n = rng.randrange(-(2 ** (bits - 1)), 2 ** (bits - 1))
        if difficulty == "easy":
            n = rng.randrange(-16, 16)
        pattern = bin_str(n & (2**bits - 1), bits)
        if rng.random() < 0.5:
            working = (
                f"{abs(n)} = {bin_str(abs(n), bits)}; flip; add 1"
                if n < 0
                else "Positive: plain binary"
            )
            out.append(
                Question(
                    f"Write {n} as an 8-bit two's complement number.", grouped(pattern), working
                )
            )
        else:
            working = "MSB is 1: negative, flip and add 1" if n < 0 else "MSB is 0: positive"
            out.append(
                Question(
                    f"What denary value is {grouped(pattern)} (two's complement)?", str(n), working
                )
            )
    return out


# ---------------------------------------------------------------- 3. binary addition
def binary_addition(seed: int, count: int, difficulty: Difficulty) -> list[Question]:
    rng = random.Random(seed)
    bits = 8
    out: list[Question] = []
    for i in range(count):
        if difficulty == "easy":
            a, b = rng.randrange(0, 2**bits // 2), rng.randrange(0, 2**bits // 2)
        elif difficulty == "hard" or i % 3 == 0:
            a, b = rng.randrange(2**bits // 2, 2**bits), rng.randrange(2**bits // 2, 2**bits)
        else:
            a, b = rng.randrange(0, 2**bits), rng.randrange(0, 2**bits)
        total = a + b
        overflow = total >= 2**bits
        result = bin_str(total & (2**bits - 1), bits)
        out.append(
            Question(
                f"Add {grouped(bin_str(a, bits))} and {grouped(bin_str(b, bits))} (8-bit). "
                "Give the result and state whether overflow occurs.",
                f"{grouped(result)}, overflow: {'yes' if overflow else 'no'}",
                f"{a} + {b} = {total}"
                + (f" (> 255, carry out of bit 7 lost: {total - 256})" if overflow else ""),
                answer_lines=2,
            )
        )
    return out


# ---------------------------------------------------------------- 4. shifts
def shifts(seed: int, count: int, difficulty: Difficulty) -> list[Question]:
    rng = random.Random(seed)
    bits = 8
    out: list[Question] = []
    for _ in range(count):
        n = rng.randrange(1, 2**bits)
        places = rng.randrange(1, 3 if difficulty != "hard" else 4)
        direction = rng.choice(["left", "right"])
        kind = "logical" if difficulty == "easy" else rng.choice(["logical", "arithmetic"])
        pattern = bin_str(n, bits)
        if direction == "left":
            result = (n << places) & (2**bits - 1)
            lost = n >> (bits - places)
            effect = f"multiplies by {2**places}" + (" but bits were lost" if lost else "")
        elif kind == "logical":
            result = n >> places
            effect = f"divides by {2**places} (integer)"
        else:
            signed = n - 2**bits if n >= 2 ** (bits - 1) else n
            result = (signed >> places) & (2**bits - 1)
            effect = f"divides by {2**places}, sign kept"
        out.append(
            Question(
                f"Apply a {kind} shift {direction} by {places} to {grouped(pattern)}. "
                "Give the result and its effect on the value.",
                f"{grouped(bin_str(result, bits))}; {effect}",
                f"{n} -> {result}",
                answer_lines=2,
            )
        )
    return out


# ---------------------------------------------------------------- 5. truth tables
_OPS: dict[str, Callable[[int, int], int]] = {
    "AND": lambda a, b: a & b,
    "OR": lambda a, b: a | b,
    "XOR": lambda a, b: a ^ b,
    "NAND": lambda a, b: 1 - (a & b),
    "NOR": lambda a, b: 1 - (a | b),
}

# What each GCSE board requires. Neither has NAND or NOR; AQA 8525 (3.4.2) has XOR, OCR J277
# (2.4.1) does not. A-level adds XOR for every board and NAND/NOR, but those only at "hard".
GCSE_GATES: dict[str, tuple[str, ...]] = {
    "ocr": ("AND", "OR", "NOT"),
    "aqa": ("AND", "OR", "NOT", "XOR"),
}
A_LEVEL_GATES: tuple[str, ...] = ("AND", "OR", "NOT", "XOR")
BEYOND_GCSE_GATES: tuple[str, ...] = ("NAND", "NOR")


def gate_set(
    board: str, level: Level = "gcse", difficulty: Difficulty = "medium"
) -> tuple[str, ...]:
    """The operators a truth-table sheet may use. An unknown board gets the OCR set,
    the smaller one, so a misconfigured board never puts off-spec gates on a sheet."""
    if level == "a_level":
        return A_LEVEL_GATES + (BEYOND_GCSE_GATES if difficulty == "hard" else ())
    return GCSE_GATES.get(board.lower(), GCSE_GATES["ocr"])


@dataclass(frozen=True)
class Expr:
    text: str
    fn: Callable[[dict[str, int]], int]
    names: frozenset[str]
    tidy: bool = True  # no gate fed the same input on both sides, no repeated sub-expression


def _leaf(name: str, negate: bool) -> Expr:
    def fn(env: dict[str, int]) -> int:
        return 1 - env[name] if negate else env[name]

    return Expr(f"NOT {name}" if negate else name, fn, frozenset({name}))


def _node(op: str, left: Expr, right: Expr) -> Expr:
    apply = _OPS[op]

    def fn(env: dict[str, int]) -> int:
        return apply(left.fn(env), right.fn(env))

    same_input = len(left.names) == 1 and left.names == right.names  # C XOR C, NOT B AND B
    tidy = left.tidy and right.tidy and not same_input and left.text != right.text
    return Expr(f"({left.text} {op} {right.text})", fn, left.names | right.names, tidy)


def _negate(expr: Expr) -> Expr:
    """NOT over a bracketed sub-expression: ``NOT (A AND B)``."""
    return Expr(f"NOT {expr.text}", lambda env: 1 - expr.fn(env), expr.names, expr.tidy)


def _shaped_expr(
    rng: random.Random, inputs: list[str], gates: list[str], difficulty: Difficulty
) -> Expr:
    """One shape per difficulty, so the three sheets are visibly different: easy is one
    gate on two inputs; medium is two gates (``(A AND B) OR NOT C``); hard is three gates
    or a NOT over a bracket (``NOT (A AND B) OR (B AND C)``)."""

    def leaf() -> Expr:
        return _leaf(rng.choice(inputs), rng.random() < 0.3)

    def gate() -> Expr:
        return _node(rng.choice(gates), leaf(), leaf())

    if difficulty == "easy":
        return gate()
    if difficulty == "medium":
        kids = [gate(), leaf()]
        rng.shuffle(kids)
        return _node(rng.choice(gates), kids[0], kids[1])
    if rng.random() < 0.5:
        return _node(rng.choice(gates), gate(), gate())
    plain = [g for g in gates if g not in BEYOND_GCSE_GATES] or gates  # NOT (A NAND B) is odd
    negated = _negate(_node(rng.choice(plain), leaf(), leaf()))
    kids = [negated, gate() if rng.random() < 0.5 else leaf()]
    rng.shuffle(kids)
    return _node(rng.choice(gates), kids[0], kids[1])


def _degenerate(expr: Expr, names: list[str], column: list[int]) -> bool:
    """A table nobody would set: an input the table lists goes unused, a gate is fed
    the same input twice, Q is constant, or Q is just one input (or its NOT)."""
    if expr.names != set(names) or not expr.tidy or len(set(column)) < 2:
        return True
    n = len(names)
    for i in range(n):
        inputs = [(combo >> (n - 1 - i)) & 1 for combo in range(2**n)]
        if column in (inputs, [1 - v for v in inputs]):
            return True
    return False


def truth_tables(
    seed: int, count: int, difficulty: Difficulty, gates: tuple[str, ...] = GCSE_GATES["ocr"]
) -> list[Question]:
    rng = random.Random(seed)
    n_inputs = 2 if difficulty == "easy" else 3
    names = ["A", "B", "C"][:n_inputs]
    binary_gates = [g for g in gates if g in _OPS]  # NOT is applied at the leaves
    envs = [
        {name: (combo >> (n_inputs - 1 - i)) & 1 for i, name in enumerate(names)}
        for combo in range(2**n_inputs)
    ]
    seen: set[str] = set()
    out: list[Question] = []
    for _ in range(count):
        for attempt in range(300):
            expr = _shaped_expr(rng, names, binary_gates, difficulty)
            column = [expr.fn(env) for env in envs]
            if _degenerate(expr, names, column):
                continue
            if expr.text in seen and attempt < 200:  # prefer a fresh question; small spaces repeat
                continue
            break
        seen.add(expr.text)
        text = (
            expr.text[1:-1] if expr.text.startswith("(") and expr.text.endswith(")") else expr.text
        )
        rows = [(*(str(env[n]) for n in names), "") for env in envs]
        out.append(
            Question(
                f"Complete the truth table for Q = {text}.",
                " ".join(str(v) for v in column) + "  (Q column, rows in table order)",
                "",
                answer_lines=0,
                table=((*names, "Q"), *rows),
            )
        )
    return out


# ---------------------------------------------------------------- 6. Boolean simplification
@dataclass(frozen=True)
class BoolExpr:
    """A small Boolean expression tree: a letter, a constant, NOT, AND or OR."""

    kind: Literal["var", "const", "not", "and", "or"]
    name: str = ""  # the letter, or "0" / "1"
    kids: tuple[BoolExpr, ...] = ()

    @property
    def text(self) -> str:
        if self.kind in ("var", "const"):
            return self.name
        if self.kind == "not":
            return f"NOT {self.kids[0].text}"
        left, right = self.kids
        return f"({left.text} {self.kind.upper()} {right.text})"

    @property
    def shown(self) -> str:
        """The text without the outermost brackets, as printed on the sheet."""
        return self.text[1:-1] if self.kind in ("and", "or") else self.text

    def letters(self) -> frozenset[str]:
        if self.kind == "var":
            return frozenset({self.name})
        return frozenset().union(*(k.letters() for k in self.kids))


def _v(name: str) -> BoolExpr:
    return BoolExpr("var", name)


def _c(bit: int) -> BoolExpr:
    return BoolExpr("const", str(bit))


def _not(x: BoolExpr) -> BoolExpr:
    return BoolExpr("not", kids=(x,))


def _neg(x: BoolExpr) -> BoolExpr:
    """NOT x with a double negation removed, as a textbook would write it."""
    return x.kids[0] if x.kind == "not" else _not(x)


def _and(a: BoolExpr, b: BoolExpr) -> BoolExpr:
    return BoolExpr("and", kids=(a, b))


def _or(a: BoolExpr, b: BoolExpr) -> BoolExpr:
    return BoolExpr("or", kids=(a, b))


def _paths(node: BoolExpr, prefix: tuple[int, ...] = ()) -> list[tuple[tuple[int, ...], BoolExpr]]:
    found = [(prefix, node)]
    for i, kid in enumerate(node.kids):
        found += _paths(kid, (*prefix, i))
    return found


def _at(node: BoolExpr, path: tuple[int, ...]) -> BoolExpr:
    for i in path:
        node = node.kids[i]
    return node


def _replace(node: BoolExpr, path: tuple[int, ...], new: BoolExpr) -> BoolExpr:
    if not path:
        return new
    head, rest = path[0], path[1:]
    kids = tuple(_replace(k, rest, new) if i == head else k for i, k in enumerate(node.kids))
    return replace(node, kids=kids)


def _is_literal(node: BoolExpr) -> bool:
    """A letter or a negated letter: what a textbook law is written over."""
    return node.kind == "var" or (node.kind == "not" and node.kids[0].kind == "var")


def _is_simple_gate(node: BoolExpr) -> bool:
    """AND/OR of two different literals, such as ``A AND NOT B``: the only gates De Morgan
    and the redundancy law are applied to, so their forms stay the ones in the textbook
    (never ``NOT (NOT B OR NOT B)`` from an idempotent ``B AND B``)."""
    return (
        node.kind in ("and", "or")
        and all(_is_literal(k) for k in node.kids)
        and node.kids[0] != node.kids[1]
    )


def _gates(node: BoolExpr) -> int:
    return (node.kind in ("and", "or")) + sum(_gates(k) for k in node.kids)


def _nesting(node: BoolExpr) -> int:
    inner = max((_nesting(k) for k in node.kids), default=0)
    return inner + (node.kind in ("and", "or"))


def _nots(node: BoolExpr) -> int:
    return (node.kind == "not") + sum(_nots(k) for k in node.kids)


def _trivial(node: BoolExpr) -> bool:
    """X AND X, NOT NOT X or a constant anywhere in the expression. Fine when the
    identities are what is being practised; otherwise not a question a teacher sets."""
    if node.kind == "const":
        return True
    if node.kind == "not" and node.kids[0].kind == "not":
        return True
    if node.kind in ("and", "or") and node.kids[0] == node.kids[1]:
        return True
    return any(_trivial(k) for k in node.kids)


def _triple_not(node: BoolExpr) -> bool:
    """NOT NOT NOT X: nobody writes it, even on an identities sheet."""
    if node.kind == "not" and node.kids[0].kind == "not" and node.kids[0].kids[0].kind == "not":
        return True
    return any(_triple_not(k) for k in node.kids)


# A law wraps a node ``x`` in a longer form that simplifies back to ``x``. Laws over a
# literal take another letter ``y``; laws over a simple gate use the gate's own operands.
# Each returns the longer form, the law's name and an optional intermediate form for the
# key, or None when it does not apply to this ``x``.
_Wrap = tuple[BoolExpr, str, str] | None
_Law = Callable[[BoolExpr, BoolExpr, random.Random], _Wrap]


def _absorption(x: BoolExpr, y: BoolExpr, rng: random.Random) -> _Wrap:
    """X OR (X AND Y) = X, and its dual; over a literal or a whole simple gate, so
    ``(A AND B) OR ((A AND B) AND C)`` can appear."""
    if rng.random() < 0.5:
        inner = _and(x, y) if rng.random() < 0.5 else _and(y, x)
        new = _or(x, inner) if rng.random() < 0.5 else _or(inner, x)
    else:
        inner = _or(x, y) if rng.random() < 0.5 else _or(y, x)
        new = _and(x, inner) if rng.random() < 0.5 else _and(inner, x)
    return new, "absorption", ""


def _combining(x: BoolExpr, y: BoolExpr, rng: random.Random) -> _Wrap:
    """(X AND Y) OR (X AND NOT Y) = X AND (Y OR NOT Y) = X, and its dual."""
    if not _is_literal(x):
        return None
    if rng.random() < 0.5:
        new, via = _or(_and(x, y), _and(x, _neg(y))), _and(x, _or(y, _neg(y)))
    else:
        new, via = _and(_or(x, y), _or(x, _neg(y))), _or(x, _and(y, _neg(y)))
    return new, "distributive then complement", via.shown


def _redundancy(x: BoolExpr, y: BoolExpr, rng: random.Random) -> _Wrap:
    """L AND R = L AND (NOT L OR R): the exam favourite ``A AND (NOT A OR B)``. The
    via form shows the distribution; the complement term then vanishes."""
    if not _is_simple_gate(x):
        return None
    left, right = x.kids
    outer, inner = (_and, _or) if x.kind == "and" else (_or, _and)
    if rng.random() < 0.5:
        new = outer(left, inner(_neg(left), right))
        via = inner(outer(left, _neg(left)), outer(left, right))
    else:
        new = outer(inner(left, _neg(right)), right)
        via = inner(outer(left, right), outer(_neg(right), right))
    return new, "distributive then complement", via.shown


def _de_morgan(x: BoolExpr, y: BoolExpr, rng: random.Random) -> _Wrap:
    """L AND R = NOT (NOT L OR NOT R), and its dual, over a simple gate only."""
    if not _is_simple_gate(x):
        return None
    left, right = x.kids
    inner = _or if x.kind == "and" else _and
    return _not(inner(_neg(left), _neg(right))), "De Morgan", ""


def _identity(x: BoolExpr, y: BoolExpr, rng: random.Random) -> _Wrap:
    if not _is_literal(x):
        return None
    forms = [_and(x, _c(1)), _and(_c(1), x), _or(x, _c(0)), _or(_c(0), x)]
    return rng.choice(forms), "identity", ""


def _idempotent(x: BoolExpr, y: BoolExpr, rng: random.Random) -> _Wrap:
    if not _is_literal(x):
        return None
    return rng.choice([_and(x, x), _or(x, x)]), "idempotent", ""


def _double_negation(x: BoolExpr, y: BoolExpr, rng: random.Random) -> _Wrap:
    if x.kind != "var":  # NOT NOT NOT A is not a question
        return None
    return _not(_not(x)), "double negation", ""


def _complement(x: BoolExpr, y: BoolExpr, rng: random.Random) -> _Wrap:
    if not _is_literal(x):
        return None
    if rng.random() < 0.5:  # X AND (Y OR NOT Y) = X AND 1 = X
        return _and(x, _or(y, _neg(y))), "complement then identity", _and(x, _c(1)).shown
    return _or(x, _and(y, _neg(y))), "complement then identity", _or(x, _c(0)).shown


# What the header says each family practises.
LAW_FAMILIES: dict[str, tuple[str, ...]] = {
    "absorption": ("absorption", "distributive", "complement"),
    "de_morgan": ("absorption", "distributive", "complement", "De Morgan"),
    "identities": ("identity", "idempotent", "double negation", "complement"),
    "all": (
        "absorption",
        "distributive",
        "complement",
        "De Morgan",
        "identity",
        "idempotent",
        "double negation",
    ),
}


def _laws_for(family: str) -> list[_Law]:
    laws: list[_Law] = []
    if family in ("absorption", "de_morgan", "all"):
        laws += [_absorption, _combining, _redundancy]
    if family in ("identities", "all"):
        laws += [_identity, _idempotent, _double_negation, _complement]
    if family in ("de_morgan", "all"):
        laws.append(_de_morgan)
    return laws


# How dense a printed question may get: (AND/OR gates, bracket nesting, NOTs). A hard
# three-step question stays the size of an exam one, ``(A OR (A AND C)) AND NOT (A AND
# NOT B)``, rather than growing a form inside a form inside a form.
_BUDGET: dict[Difficulty, tuple[int, int, int]] = {
    "easy": (3, 2, 3),
    "medium": (5, 3, 3),
    "hard": (6, 3, 4),
}


def _targets() -> list[BoolExpr]:
    a, b = _v("A"), _v("B")
    return [
        _v("A"),
        _v("B"),
        _v("C"),
        _and(a, b),
        _or(a, b),
        _not(a),
        _and(a, _not(b)),
        _or(_not(a), b),
    ]


def _other_letter(rng: random.Random, node: BoolExpr, whole: BoolExpr) -> BoolExpr:
    """A letter that is not the one being wrapped, preferring one the question does
    not use yet so sheets read A, B, C rather than A, A, A. Sometimes negated."""
    unused = [n for n in "ABC" if n not in whole.letters() and n not in node.letters()]
    pool = unused or [n for n in "ABC" if n not in node.letters()] or list("ABC")
    letter = _v(rng.choice(pool))  # the last fallback is for a gate that uses every letter
    return _neg(letter) if rng.random() < 0.3 else letter


@dataclass(frozen=True)
class _Candidate:
    law: str
    new: BoolExpr  # the longer form
    old: BoolExpr  # the node it replaces
    via: str
    result: BoolExpr  # the whole expression after the wrap


def _candidates(
    expr: BoolExpr, laws: list[_Law], rng: random.Random, allow_trivial: bool
) -> list[_Candidate]:
    """Every clean way of applying one law somewhere in ``expr``: over a literal, or over
    a simple gate. De Morgan is never applied directly under a NOT, which would print
    ``NOT NOT (...)`` and credit De Morgan for a double negation."""
    found: list[_Candidate] = []
    for path, node in _paths(expr):
        if not (_is_literal(node) or _is_simple_gate(node)):
            continue
        under_not = bool(path) and _at(expr, path[:-1]).kind == "not"
        for law in laws:
            if law is _de_morgan and under_not:
                continue
            wrap = law(node, _other_letter(rng, node, expr), rng)
            if wrap is None:
                continue
            new, name, via = wrap
            candidate = _replace(expr, path, new)
            if _triple_not(candidate) or (_trivial(candidate) and not allow_trivial):
                continue
            found.append(_Candidate(name, new, node, via, candidate))
    return found


def _within(candidate: _Candidate, budget: tuple[int, int, int]) -> bool:
    gates, nesting, nots = budget
    result = candidate.result
    return _gates(result) <= gates and _nesting(result) <= nesting and _nots(result) <= nots


def _wrap_chain(
    expr: BoolExpr,
    remaining: int,
    family: list[_Law],
    rng: random.Random,
    allow_trivial: bool,
    budget: tuple[int, int, int],
    used: frozenset[str],
    need: int,
) -> list[_Candidate] | None:
    """``remaining`` wraps in a row that all stay within the budget and name at least
    ``need`` different laws between them, chosen at random but preferring a law the
    question has not used yet; None when no sequence fits. A wrap is only committed to
    when the steps after it can still fit, so a question never has to exceed its budget
    to reach its step count, and a two-step key never practises one law twice."""
    if remaining == 0:
        return [] if len(used) >= need else None
    options = [c for c in _candidates(expr, family, rng, allow_trivial) if _within(c, budget)]
    rng.shuffle(options)
    options.sort(key=lambda c: c.law in used)  # stable: fresh laws first, shuffled within
    for candidate in options:
        rest = _wrap_chain(
            candidate.result,
            remaining - 1,
            family,
            rng,
            allow_trivial,
            budget,
            used | {candidate.law},
            need,
        )
        if rest is not None:
            return [candidate, *rest]
    return None


def boolean_simplification(
    seed: int, count: int, difficulty: Difficulty, laws: Laws = "absorption"
) -> list[Question]:
    """Start from a short target and wrap one literal or one simple gate at a time in a
    law's textbook form, keeping the whole within the difficulty's size budget and
    preferring a law the question has not used yet. The key undoes the wraps in reverse
    order, each step written with the actual sub-expression it rewrites, so it reads in
    the question's own letters and ends at the target."""
    rng = random.Random(seed)
    steps_n = {"easy": 1, "medium": 2, "hard": 3}[difficulty]
    budget = _BUDGET[difficulty]
    family = _laws_for(laws)
    allow_trivial = laws in ("identities", "all")
    targets = _targets()
    seen: set[str] = set()
    out: list[Question] = []
    for _ in range(count):
        found: tuple[BoolExpr, list[_Candidate]] | None = None
        for _attempt in range(20):  # prefer a question the sheet does not already have
            target = rng.choice(targets)
            chain = _wrap_chain(
                target, steps_n, family, rng, allow_trivial, budget, frozenset(), min(2, steps_n)
            )
            if chain is None:  # this target cannot carry that many steps within the budget
                continue
            found = (target, chain)
            if chain[-1].result.shown not in seen:
                break
        if found is None:  # pragma: no cover - every target carries three steps
            msg = f"no {difficulty} question fits the size budget for laws={laws!r}"
            raise RuntimeError(msg)
        target, wraps = found
        expr = wraps[-1].result
        seen.add(expr.shown)
        # Undoing a wrap leaves the expression it was applied to: the previous wrap's
        # result, or the target for the first wrap.
        before_each = [target, *(w.result for w in wraps[:-1])]
        steps = tuple(
            Step(law=w.law, before=w.new.shown, after=w.old.shown, result=s.shown, via=w.via)
            for w, s in zip(reversed(wraps), reversed(before_each), strict=True)
        )
        working = "\n".join(f"{i}. {step.text()}" for i, step in enumerate(steps, 1))
        out.append(
            Question(
                f"Simplify: {expr.shown}",
                target.shown,
                working,
                answer_lines=2 + steps_n,
                steps=steps,
            )
        )
    return out


# ---------------------------------------------------------------- 7. file sizes
def file_size(seed: int, count: int, difficulty: Difficulty) -> list[Question]:
    rng = random.Random(seed)
    out: list[Question] = []
    for _ in range(count):
        kind = rng.choice(["image", "sound", "text"])
        if kind == "image":
            w, h = rng.choice([(100, 100), (640, 480), (800, 600), (1024, 768), (1920, 1080)])
            depth = rng.choice([1, 2, 4, 8, 24]) if difficulty != "easy" else rng.choice([1, 8])
            bits = w * h * depth
            out.append(
                Question(
                    f"An image is {w} × {h} pixels with a colour depth of {depth} bits. "
                    "Calculate its file size in bytes (and KB, 1 KB = 1000 bytes).",
                    f"{bits // 8} bytes = {bits / 8 / 1000:g} KB",
                    f"{w} × {h} × {depth} = {bits} bits ÷ 8",
                    answer_lines=2,
                )
            )
        elif kind == "sound":
            rate = rng.choice([8000, 22050, 44100]) if difficulty != "easy" else 8000
            res = rng.choice([8, 16]) if difficulty != "easy" else 8
            secs = rng.choice([1, 5, 10, 30, 60])
            channels = 2 if difficulty == "hard" and rng.random() < 0.5 else 1
            bits = rate * res * secs * channels
            out.append(
                Question(
                    f"A sound is sampled at {rate} Hz with a resolution of {res} bits for {secs} s"
                    + (" in stereo (2 channels)" if channels == 2 else "")
                    + ". Calculate its size in bytes (and KB).",
                    f"{bits // 8} bytes = {bits / 8 / 1000:g} KB",
                    f"{rate} × {res} × {secs}"
                    + (" × 2" if channels == 2 else "")
                    + f" = {bits} bits ÷ 8",
                    answer_lines=2,
                )
            )
        else:
            chars = rng.choice([100, 250, 500, 1000, 2000, 5000])
            per = rng.choice([7, 8, 16]) if difficulty != "easy" else 8
            bits = chars * per
            out.append(
                Question(
                    f"A text file has {chars} characters stored at {per} bits each. "
                    "Calculate its size in bytes.",
                    f"{bits // 8} bytes" if bits % 8 == 0 else f"{bits / 8:g} bytes",
                    f"{chars} × {per} = {bits} bits ÷ 8",
                )
            )
    return out


# ---------------------------------------------------------------- 8. run-length encoding
def rle_encode(text: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(text):
        j = i
        while j < len(text) and text[j] == text[i]:
            j += 1
        out.append(f"{j - i}{text[i]}")
        i = j
    return " ".join(out)


def rle(seed: int, count: int, difficulty: Difficulty) -> list[Question]:
    rng = random.Random(seed)
    alphabet = "AB" if difficulty == "easy" else "ABCW"
    runs = {"easy": 3, "medium": 5, "hard": 8}[difficulty]
    out: list[Question] = []
    for _ in range(count):
        text = ""
        last = ""
        for _ in range(runs):
            ch = rng.choice([c for c in alphabet if c != last])
            text += ch * rng.randrange(1, 7)
            last = ch
        if rng.random() < 0.7:
            out.append(
                Question(f"Run-length encode: {text}", rle_encode(text), f"{len(text)} characters")
            )
        else:
            out.append(Question(f"Decode the run-length encoding: {rle_encode(text)}", text))
    return out


# ---------------------------------------------------------------- 9. Huffman
def huffman_weight(freqs: dict[str, int]) -> int:
    """Total bits = sum(freq * depth), computed by merging the two lightest
    weights; equivalently the sum of all internal node weights."""
    heap = list(freqs.values())
    heapq.heapify(heap)
    total = 0
    while len(heap) > 1:
        a, b = heapq.heappop(heap), heapq.heappop(heap)
        total += a + b
        heapq.heappush(heap, a + b)
    return total if len(freqs) > 1 else sum(freqs.values())


def huffman(seed: int, count: int, difficulty: Difficulty) -> list[Question]:
    rng = random.Random(seed)
    symbols_n = {"easy": 3, "medium": 4, "hard": 6}[difficulty]
    out: list[Question] = []
    for _ in range(count):
        letters = rng.sample("ABCDEFGH", symbols_n)
        freqs = {ch: rng.randrange(1, 12) for ch in letters}
        total_chars = sum(freqs.values())
        bits = huffman_weight(freqs)
        fixed = total_chars * max(1, (symbols_n - 1).bit_length())
        table = ", ".join(f"{ch}: {f}" for ch, f in freqs.items())
        out.append(
            Question(
                f"Build a Huffman tree for the frequencies {table}. "
                "How many bits does the compressed message use? "
                f"(Fixed-length would need {fixed} bits.)",
                f"{bits} bits",
                "Merge the two smallest weights repeatedly; total = sum of merged weights.",
                answer_lines=3,
            )
        )
    return out


GENERATORS: dict[str, Generator] = {
    "binary": binary,
    "twos_complement": twos_complement,
    "binary_addition": binary_addition,
    "shifts": shifts,
    "truth_tables": truth_tables,
    "boolean_simplification": boolean_simplification,
    "file_size": file_size,
    "rle": rle,
    "huffman": huffman,
}

TOPIC_TITLES: dict[str, str] = {
    "binary": "Binary, denary and hexadecimal",
    "twos_complement": "Two's complement",
    "binary_addition": "Binary addition and overflow",
    "shifts": "Logical and arithmetic shifts",
    "truth_tables": "Truth tables",
    "boolean_simplification": "Boolean simplification",
    "file_size": "File size calculations",
    "rle": "Run-length encoding",
    "huffman": "Huffman coding",
}


def generate(
    topic: str,
    seed: int,
    count: int,
    difficulty: Difficulty,
    *,
    board: str = "ocr",
    level: Level = "gcse",
    laws: Laws = "absorption",
) -> list[Question]:
    """``board`` is the teacher's exam board from config (``ocr`` or ``aqa``); it and
    ``level`` decide the gates a truth table may use, ``laws`` the simplification family.
    A ``count`` outside ``MIN_COUNT``..``MAX_COUNT`` is refused: an empty sheet and key
    help nobody, and a 500-question sheet is a typo."""
    try:
        gen = GENERATORS[topic]
    except KeyError:
        msg = f"unknown topic {topic!r}; choose from {', '.join(GENERATORS)}"
        raise ValueError(msg) from None
    if not MIN_COUNT <= count <= MAX_COUNT:
        msg = f"Questions must be between {MIN_COUNT} and {MAX_COUNT} (you asked for {count})."
        raise ValueError(msg)
    if topic == "truth_tables":
        return truth_tables(seed, count, difficulty, gate_set(board, level, difficulty))
    if topic == "boolean_simplification":
        return boolean_simplification(seed, count, difficulty, laws)
    return gen(seed, count, difficulty)


def header_note(options: Options, board: str) -> str:
    """What the sheet header must state beyond seed and difficulty for the set to be
    trusted and regenerated: the gate set for truth tables, the laws for simplification."""
    if options.topic == "truth_tables":
        gates = ", ".join(gate_set(board, options.level, options.difficulty))
        prefix = "A-level · " if options.level == "a_level" else ""
        return f"{prefix}gates: {gates}"
    if options.topic == "boolean_simplification":
        return "laws: " + ", ".join(LAW_FAMILIES[options.laws])
    return ""
