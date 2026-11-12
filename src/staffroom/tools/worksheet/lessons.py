"""Units and lessons (#75): one sheet practises one skill.

A unit (*Binary & hex*) holds lessons (*Denary to binary*). A lesson sheet opens with a
one-line aim and a worked example solved in full, then climbs through Warm-up, Practice
and Stretch; Difficulty moves the whole climb up or down. Each lesson names the spec
point it serves on every GCSE board, checked against ``core/spec/*.toml`` and the
published specifications (see ``SPEC_SOURCES``).

A Review lesson is the sheet the tool made before lessons existed, from the same
generator in ``logic``: an old seed still makes the same sheet and key. Each old topic
name is the Review of its unit, so ``--topic binary`` keeps working.

Pure: no files, no Qt. Answers are checked by independent computation in the tests.
"""

from __future__ import annotations

import heapq
import random
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from staffroom.tools.worksheet.logic import (
    BEYOND_GCSE_GATES,
    LAW_FAMILIES,
    Difficulty,
    Expr,
    Laws,
    Level,
    Question,
    _degenerate,
    _leaf,
    _negate,
    _node,
    bin_str,
    gate_set,
    grouped,
    rle_encode,
    simplify_question,
)

SECTIONS = ("Warm-up", "Practice", "Stretch")
PLACES = (128, 64, 32, 16, 8, 4, 2, 1)
Range = tuple[int, int]
Ranges = tuple[Range, Range, Range]  # the size of a question in each section


# ---------------------------------------------------------------- what a sheet holds
@dataclass(frozen=True)
class Example:
    """A question solved in full on the sheet: the working, one step a line, and the
    answer, with a table where one helps (place values, a column addition)."""

    question: str
    steps: tuple[str, ...]
    answer: str
    table: tuple[tuple[str, ...], ...] | None = None  # columns, then rows


@dataclass(frozen=True)
class Part:
    name: str  # Warm-up, Practice, Stretch
    hint: str  # what the section holds, small beside its name: "1 to 31"
    questions: tuple[Question, ...]


@dataclass(frozen=True)
class LessonSheet:
    aim: str
    example: Example
    parts: tuple[Part, ...]

    @property
    def questions(self) -> list[Question]:
        return [q for part in self.parts for q in part.questions]


@dataclass(frozen=True)
class Settings:
    """What a lesson may read besides seed and difficulty."""

    board: str = "ocr"
    level: Level = "gcse"
    laws: Laws = "absorption"


QuestionMaker = Callable[[random.Random, Difficulty, int, Settings], Question]
ExampleMaker = Callable[[random.Random, Difficulty, Settings], Example]


@dataclass(frozen=True)
class Lesson:
    unit: str
    slug: str
    title: str
    what: str  # one line under the title in the panel
    spec: Mapping[str, str] = field(default_factory=dict)  # board -> spec point; {}: A level
    aim: str = ""
    kinds: tuple[str, ...] = ()  # the only question kinds the sheet may hold
    ranges: Callable[[Difficulty], Ranges] | None = None
    hints: Callable[[Difficulty], tuple[str, str, str]] | None = None
    question: QuestionMaker | None = None
    example: ExampleMaker | None = None
    legacy: str = ""  # a Review: the old topic whose sheet it makes, unchanged
    covers: tuple[str, ...] = ()  # a Review: the unit's lessons it mixes
    uses: tuple[str, ...] = ()  # the extra settings it reads: "level", "laws"

    @property
    def key(self) -> str:
        return f"{self.unit}/{self.slug}"

    @property
    def review(self) -> bool:
        return bool(self.legacy)


@dataclass(frozen=True)
class Unit:
    slug: str
    title: str
    lessons: tuple[Lesson, ...]


# ---------------------------------------------------------------- shared pieces
def _split(count: int) -> tuple[int, int, int]:
    """How many questions each section gets: about 30% warm-up, 20% stretch."""
    if count < 3:
        return (count - 1, 1, 0) if count else (0, 0, 0)
    warm = max(1, round(count * 0.3))
    stretch = max(1, round(count * 0.2))
    return warm, count - warm - stretch, stretch


def _powers(n: int) -> list[int]:
    return [p for p in PLACES if n & p]


def _sum_text(n: int) -> str:
    return " + ".join(str(p) for p in _powers(n)) or "0"


def _place_table(n: int) -> tuple[tuple[str, ...], ...]:
    return (tuple(str(p) for p in PLACES), tuple(bin_str(n, 8)))


def _number_ranges(difficulty: Difficulty) -> Ranges:
    """8-bit numbers: each section's range sits above the last."""
    return {
        "easy": ((1, 15), (16, 63), (64, 127)),
        "medium": ((1, 31), (32, 127), (128, 255)),
        "hard": ((16, 63), (64, 191), (192, 255)),
    }[difficulty]


def _range_hints(ranges: Ranges, unit: str = "") -> tuple[str, str, str]:
    a, b, c = (f"{lo} to {hi}{unit}" for lo, hi in ranges)
    return a, b, c


def _number_hints(difficulty: Difficulty) -> tuple[str, str, str]:
    return _range_hints(_number_ranges(difficulty))


def _pick(rng: random.Random, rng_range: Range) -> int:
    lo, hi = rng_range
    return rng.randint(lo, hi)


def _hex(n: int) -> str:
    return format(n, "X") if n < 16 else format(n, "02X")


def _width(n: int) -> int:
    return 4 if n < 16 else 8


# ---------------------------------------------------------------- Binary & hex
def _d2b(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    n = _pick(rng, _number_ranges(d)[tier])
    return Question(
        f"Convert {n} to binary (8 bits).",
        grouped(bin_str(n, 8)),
        f"{n} = {_sum_text(n)}",
        kind="d2b",
        size=n,
    )


def _d2b_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    n = _pick(rng, _number_ranges(d)[1])
    return Example(
        f"Convert {n} to binary (8 bits).",
        (
            f"Take the largest place values that fit: {n} = {_sum_text(n)}.",
            "Write 1 under each of those and 0 under the rest.",
        ),
        grouped(bin_str(n, 8)),
        _place_table(n),
    )


def _b2d(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    n = _pick(rng, _number_ranges(d)[tier])
    return Question(
        f"Convert {grouped(bin_str(n, 8))} to denary.",
        str(n),
        f"{_sum_text(n)} = {n}",
        kind="b2d",
        size=n,
    )


def _b2d_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    n = _pick(rng, _number_ranges(d)[1])
    return Example(
        f"Convert {grouped(bin_str(n, 8))} to denary.",
        (
            "Write the bits under the place values.",
            f"Add the place values that hold a 1: {_sum_text(n)} = {n}.",
        ),
        str(n),
        _place_table(n),
    )


def _hex_ranges(difficulty: Difficulty) -> Ranges:
    """One hex digit to warm up, then two."""
    return {
        "easy": ((1, 9), (10, 15), (16, 79)),
        "medium": ((1, 15), (16, 159), (160, 255)),
        "hard": ((10, 15), (16, 191), (160, 255)),
    }[difficulty]


def _hex_hints(difficulty: Difficulty) -> tuple[str, str, str]:
    return tuple(  # type: ignore[return-value]
        "one hex digit" if hi < 16 else "two hex digits" for _lo, hi in _hex_ranges(difficulty)
    )


def _nibbles(n: int) -> list[str]:
    b = bin_str(n, _width(n))
    return [b[i : i + 4] for i in range(0, len(b), 4)]


def _nibble_working(n: int) -> str:
    return ", ".join(f"{nib} = {format(int(nib, 2), 'X')}" for nib in _nibbles(n))


def _bin_hex(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    n = _pick(rng, _hex_ranges(d)[tier])
    b = grouped(bin_str(n, _width(n)))
    if rng.random() < 0.5:
        return Question(
            f"Convert {b} (binary) to hexadecimal.",
            _hex(n),
            _nibble_working(n),
            kind="b2h",
            size=n,
        )
    return Question(
        f"Convert {_hex(n)} (hex) to binary ({_width(n)} bits).",
        b,
        _nibble_working(n),
        kind="h2b",
        size=n,
    )


def _bin_hex_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    n = rng.randint(160, 255)  # two digits, at least one a letter
    nibbles = _nibbles(n)
    return Example(
        f"Convert {grouped(bin_str(n, 8))} (binary) to hexadecimal.",
        (
            "Split the byte into two nibbles (groups of 4 bits).",
            "Turn each nibble into one hex digit (8 4 2 1; 10 to 15 are A to F): "
            + _nibble_working(n)
            + ".",
        ),
        _hex(n),
        (("Nibble", *nibbles), ("Hex", *(format(int(x, 2), "X") for x in nibbles))),
    )


def _hex_value(digit: str) -> str:
    v = int(digit, 16)
    return f"{digit} = {v}" if v > 9 else digit


def _den_hex(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    n = _pick(rng, _hex_ranges(d)[tier])
    h = _hex(n)
    if rng.random() < 0.5:
        return Question(
            f"Convert {n} to hexadecimal.",
            h,
            f"{n} ÷ 16 = {n // 16} remainder {n % 16}, so {h}",
            kind="d2h",
            size=n,
        )
    high, low = divmod(n, 16)
    return Question(
        f"Convert {h} (hex) to denary.",
        str(n),
        f"{high} × 16 + {low} = {n}" + (f"  ({', '.join(_hex_value(c) for c in h)})"),
        kind="h2d",
        size=n,
    )


def _den_hex_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    n = rng.randint(160, 255)
    high, low = divmod(n, 16)
    h = _hex(n)
    return Example(
        f"Convert {n} to hexadecimal.",
        (
            f"How many 16s fit in {n}? {n} ÷ 16 = {high} remainder {low}.",
            f"{high} sixteens and {low} ones. Write each as one hex digit "
            f"(10 to 15 are A to F): {h[0]} and {h[1]}.",
            f"Check: {high} × 16 + {low} = {n}.",
        ),
        h,
        (("16s", "1s"), (h[0], h[1])),
    )


# ---------------------------------------------------------------- Binary arithmetic
def _carries(a: int, b: int) -> str:
    """The carry written above each column of a + b (8 bits, left to right)."""
    marks = []
    carry = 0
    for bit in range(8):
        total = ((a >> bit) & 1) + ((b >> bit) & 1) + carry
        marks.append("1" if carry else "")
        carry = total >> 1
    return " ".join(m or "-" for m in reversed(marks))


def _carry_row(a: int, b: int) -> tuple[str, ...]:
    return tuple("" if m == "-" else m for m in _carries(a, b).split())


def _addition(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    lo, hi = _number_ranges(d)[tier]
    total = rng.randint(max(lo, 2), hi)
    a = rng.randint(1, total - 1)
    b = total - a
    return Question(
        f"Add {grouped(bin_str(a, 8))} and {grouped(bin_str(b, 8))}.",
        grouped(bin_str(total, 8)),
        f"{a} + {b} = {total}; carries: {_carries(a, b)}",
        answer_lines=2,
        kind="add",
        size=total,
    )


def _addition_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    for _ in range(50):  # one with a few carries, so the example shows them
        total = rng.randint(40, 200)
        a = rng.randint(1, total - 1)
        b = total - a
        if _carries(a, b).count("1") >= 2:
            break
    return Example(
        f"Add {grouped(bin_str(a, 8))} and {grouped(bin_str(b, 8))}.",
        (
            "Work from the right. 0 + 0 = 0, 0 + 1 = 1, 1 + 1 = 0 carry 1, 1 + 1 + 1 = 1 carry 1.",
            "Write each carry above the next column to the left.",
            f"Check in denary: {a} + {b} = {a + b}.",
        ),
        grouped(bin_str(a + b, 8)),
        (
            ("", *(str(p) for p in PLACES)),
            ("Carry", *_carry_row(a, b)),
            ("", *bin_str(a, 8)),
            ("+", *bin_str(b, 8)),
            ("=", *bin_str(a + b, 8)),
        ),
    )


def _overflow_ranges(difficulty: Difficulty) -> Ranges:
    """The sum: warm-up near 255, the stretch always over it."""
    return {
        "easy": ((100, 300), (180, 380), (256, 400)),
        "medium": ((150, 300), (200, 420), (256, 480)),
        "hard": ((200, 330), (240, 460), (300, 510)),
    }[difficulty]


def _overflow(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    total = _pick(rng, _overflow_ranges(d)[tier])
    a = rng.randint(max(1, total - 255), min(255, total - 1))
    b = total - a
    stored = total & 255
    over = total > 255
    prompt = (
        f"Add {grouped(bin_str(a, 8))} and {grouped(bin_str(b, 8))} (8-bit). "
        "Give the result and state whether overflow occurs."
    )
    answer = f"{grouped(bin_str(stored, 8))}, overflow: {'yes' if over else 'no'}"
    if tier == 2:
        prompt += " What denary value is stored, and what should it be?"
        answer += f"; stores {stored}, should be {total}"
    working = f"{a} + {b} = {total}" + (
        f" (> 255: the carry out of bit 7 is lost, leaving {stored})" if over else " (fits)"
    )
    return Question(prompt, answer, working, answer_lines=2, kind="overflow", size=total)


def _overflow_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    total = rng.randint(280, 400)
    a = rng.randint(total - 255, 255)
    b = total - a
    stored = total & 255
    return Example(
        f"Add {grouped(bin_str(a, 8))} and {grouped(bin_str(b, 8))} (8-bit). Does overflow occur?",
        (
            "Add column by column, carrying as usual.",
            "The last carry goes out of bit 7. An 8-bit register has nowhere to keep it.",
            f"In denary: {a} + {b} = {total}, more than 255, so only {stored} is stored.",
        ),
        f"{grouped(bin_str(stored, 8))}, overflow: yes",
        (
            ("", "Carry out", *(str(p) for p in PLACES)),
            ("", "", *bin_str(a, 8)),
            ("+", "", *bin_str(b, 8)),
            ("=", "1", *bin_str(stored, 8)),
        ),
    )


def _shift_ranges(difficulty: Difficulty) -> Ranges:
    """Places shifted."""
    return {
        "easy": ((1, 1), (1, 2), (2, 2)),
        "medium": ((1, 1), (1, 2), (2, 3)),
        "hard": ((1, 2), (2, 3), (3, 4)),
    }[difficulty]


def _shift_hints(difficulty: Difficulty) -> tuple[str, str, str]:
    def text(r: Range) -> str:
        lo, hi = r
        return f"{lo} place" + ("s" if lo > 1 else "") if lo == hi else f"{lo} or {hi} places"

    a, b, c = (text(r) for r in _shift_ranges(difficulty))
    return a + ", no bits lost", b, c


def _logical_shift(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    places = _pick(rng, _shift_ranges(d)[tier])
    direction = rng.choice(["left", "right"])
    for _ in range(100):
        n = rng.randint(1, 255)
        lost = (n >> (8 - places)) if direction == "left" else n & (2**places - 1)
        if tier > 0 or not lost:  # the warm-up loses no bits
            break
    if direction == "left":
        result = (n << places) & 255
        effect = f"multiplies by {2**places}" + (" but bits were lost" if lost else "")
    else:
        result = n >> places
        effect = f"divides by {2**places}" + (" (the remainder is lost)" if lost else "")
    return Question(
        f"Apply a logical shift {direction} by {places} to {grouped(bin_str(n, 8))}. "
        "Give the result and its effect on the value.",
        f"{grouped(bin_str(result, 8))}; {effect}",
        f"{n} -> {result}",
        answer_lines=2,
        kind="lshift",
        size=places,
    )


def _logical_shift_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    n = rng.randint(3, 31) * 2 + 1  # odd, under 64: a left shift by 2 loses nothing
    result = (n << 2) & 255
    return Example(
        f"Apply a logical shift left by 2 to {grouped(bin_str(n, 8))}. "
        "Give the result and its effect on the value.",
        (
            "Move every bit 2 places to the left.",
            "Bits that fall off the left end are lost; fill the gaps on the right with 0.",
            f"In denary: {n} becomes {result}. Each place left multiplies by 2, "
            "so 2 places multiplies by 4.",
        ),
        f"{grouped(bin_str(result, 8))}; multiplies by 4",
        (
            ("", *(str(p) for p in PLACES)),
            ("Before", *bin_str(n, 8)),
            ("After", *bin_str(result, 8)),
        ),
    )


def _signed(n: int) -> int:
    return n - 256 if n >= 128 else n


def _arithmetic_shift(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    places = _pick(rng, _shift_ranges(d)[tier])
    value = rng.randint(1, 127) if tier == 0 else rng.randint(-128, -1)
    pattern = value & 255
    after = value >> places  # Python's >> on an int is an arithmetic shift
    return Question(
        f"Apply an arithmetic shift right by {places} to {grouped(bin_str(pattern, 8))} "
        "(two's complement). Give the result and the denary value before and after.",
        f"{grouped(bin_str(after & 255, 8))}; {value} -> {after}",
        f"Copy the sign bit ({bin_str(pattern, 8)[0]}) into the gaps; "
        f"divides by {2**places}, rounding down",
        answer_lines=2,
        kind="ashift",
        size=places,
    )


def _arithmetic_shift_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    value = -4 * rng.randint(3, 30)
    after = value >> 2
    return Example(
        f"Apply an arithmetic shift right by 2 to {grouped(bin_str(value & 255, 8))} "
        "(two's complement). Give the result and the denary value before and after.",
        (
            "Move every bit 2 places to the right; bits that fall off the right end are lost.",
            "Fill the gaps on the left with copies of the sign bit (here 1), "
            "so a negative number stays negative.",
            f"In denary: {value} becomes {after}. Each place right halves the value.",
        ),
        f"{grouped(bin_str(after & 255, 8))}; {value} -> {after}",
        (
            ("", "-128", *(str(p) for p in PLACES[1:])),
            ("Before", *bin_str(value & 255, 8)),
            ("After", *bin_str(after & 255, 8)),
        ),
    )


# ---------------------------------------------------------------- Two's complement
def _tc_ranges(difficulty: Difficulty) -> Ranges:
    """How far below zero."""
    return {
        "easy": ((1, 8), (9, 40), (41, 100)),
        "medium": ((1, 15), (16, 100), (101, 128)),
        "hard": ((16, 63), (64, 120), (100, 128)),
    }[difficulty]


def _tc_hints(difficulty: Difficulty) -> tuple[str, str, str]:
    a, b, c = (f"-{lo} to -{hi}" for lo, hi in _tc_ranges(difficulty))
    return a, b, c


def _flip(bits: str) -> str:
    return bits.translate(str.maketrans("01", "10"))


def _to_tc(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    m = _pick(rng, _tc_ranges(d)[tier])
    plain = bin_str(m, 8)
    return Question(
        f"Write -{m} as an 8-bit two's complement number.",
        grouped(bin_str(-m & 255, 8)),
        f"{m} = {grouped(plain)}; flip: {grouped(_flip(plain))}; add 1",
        kind="to_tc",
        size=m,
    )


def _to_tc_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    m = rng.randint(20, 100)
    plain = bin_str(m, 8)
    return Example(
        f"Write -{m} as an 8-bit two's complement number.",
        (
            f"Write {m} in binary: {grouped(plain)}.",
            f"Flip every bit: {grouped(_flip(plain))}.",
            "Add 1.",
            f"Check: -128 + {_sum_text(-m & 127)} = -{m}." if -m & 127 else "",
        ),
        grouped(bin_str(-m & 255, 8)),
        (
            ("", "-128", *(str(p) for p in PLACES[1:])),
            (f"{m}", *plain),
            ("Flip", *_flip(plain)),
            ("Add 1", *bin_str(-m & 255, 8)),
        ),
    )


def _from_tc(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    m = _pick(rng, _tc_ranges(d)[tier])
    pattern = -m & 255
    rest = pattern & 127
    return Question(
        f"What denary value is {grouped(bin_str(pattern, 8))} (two's complement)?",
        str(-m),
        f"-128 + {_sum_text(rest)} = {-m}" if rest else "-128",
        kind="from_tc",
        size=m,
    )


def _from_tc_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    m = rng.randint(20, 100)
    pattern = -m & 255
    return Example(
        f"What denary value is {grouped(bin_str(pattern, 8))} (two's complement)?",
        (
            "The leftmost bit is worth -128, the rest as usual.",
            "The sign bit is 1, so the number is negative.",
            f"Add the place values that hold a 1: -128 + {_sum_text(pattern & 127)} = {-m}.",
        ),
        str(-m),
        (("-128", *(str(p) for p in PLACES[1:])), tuple(bin_str(pattern, 8))),
    )


# ---------------------------------------------------------------- Logic
NAMES = ("A", "B", "C")


@dataclass(frozen=True)
class _Shape:
    inputs: int
    gates: int  # AND / OR / XOR between two operands
    nots: int  # NOT on an input or over a bracket


def _logic_shapes(lesson: str, difficulty: Difficulty) -> tuple[_Shape, _Shape, _Shape]:
    gates, inputs = {"one-gate": (1, 2), "two-gates": (2, 3), "three-gates": (3, 3)}[lesson]
    nots = {"easy": (0, 0, 1), "medium": (0, 1, 2), "hard": (1, 2, 2)}[difficulty]
    if lesson == "one-gate" and difficulty == "easy":
        nots = (0, 1, 1)  # one plain gate has only a few tables: practise NOT sooner
    a, b, c = (_Shape(inputs, gates, k) for k in nots)
    return a, b, c


def _shaped(
    rng: random.Random, shape: _Shape, ops: list[str], names: list[str]
) -> tuple[Expr, list[Expr]]:
    """A random expression with exactly ``shape.gates`` binary gates and ``shape.nots``
    NOTs, built bottom-up so each NOT lands on a distinct input or bracket; with the
    gates and NOTs inside it in the order they are worked out, for the key."""
    leaves = names + [rng.choice(names) for _ in range(shape.gates + 1 - len(names))]
    if shape.gates > 1:  # one gate reads A then B, as the board's own tables do
        rng.shuffle(leaves)
    slots = 2 * shape.gates + 1  # leaves plus gates: where a NOT can go
    # The root may take a NOT only when it is a gate inside the tree, never alone.
    negated = set(rng.sample(range(slots - 1), min(shape.nots, slots - 1)))
    counter = iter(range(slots))
    nodes: list[Expr] = []
    steps: list[Expr] = []
    for name in leaves:
        leaf = _leaf(name, next(counter) in negated)
        if leaf.text.startswith("NOT") and leaf.text not in (x.text for x in steps):
            steps.append(leaf)
        nodes.append(leaf)
    while len(nodes) > 1:
        i = rng.randrange(len(nodes) - 1)
        node = _node(rng.choice(ops), nodes[i], nodes[i + 1])
        steps.append(node)
        if next(counter) in negated:
            node = _negate(node)
            steps.append(node)
        nodes[i : i + 2] = [node]
    return nodes[0], steps[:-1]


def _names(rng: random.Random, shape: _Shape) -> list[str]:
    """The inputs: all three, or any two of A, B and C for a one-gate table, so a short
    warm-up of AND and OR need not repeat itself."""
    if shape.inputs == len(NAMES):
        return list(NAMES)
    return sorted(rng.sample(NAMES, shape.inputs))


def _strip(text: str) -> str:
    return text[1:-1] if text.startswith("(") and text.endswith(")") else text


def _columns(expr: Expr, envs: list[dict[str, int]]) -> list[int]:
    return [expr.fn(env) for env in envs]


def _envs(names: list[str]) -> list[dict[str, int]]:
    n = len(names)
    return [
        {name: (combo >> (n - 1 - i)) & 1 for i, name in enumerate(names)} for combo in range(2**n)
    ]


def _ops_for(s: Settings, d: Difficulty) -> list[str]:
    return [g for g in gate_set(s.board, s.level, d) if g != "NOT"]


def _ops_count(text: str) -> int:
    words = text.replace("(", " ").replace(")", " ").split()
    return sum(w in ("AND", "OR", "XOR", "NAND", "NOR", "NOT") for w in words)


def _truth_table_question(
    rng: random.Random, shape: _Shape, s: Settings, d: Difficulty, kind: str
) -> Question:
    ops = _ops_for(s, d)
    names = _names(rng, shape)
    envs = _envs(names)
    expr, inner = _shaped(rng, shape, ops, names)
    for _ in range(300):
        expr, inner = _shaped(rng, shape, ops, names)
        if not _degenerate(expr, names, _columns(expr, envs)):
            break
    column = _columns(expr, envs)
    text = _strip(expr.text)
    rows = [(*(str(env[n]) for n in names), "") for env in envs]
    working = "\n".join(
        f"{_strip(x.text)}: {' '.join(str(v) for v in _columns(x, envs))}" for x in inner
    )
    if not working:  # one plain gate: the key states its rule
        op = next(w for w in text.split() if w in GATE_RULES)
        working = GATE_RULES[op]
    return Question(
        f"Complete the truth table for Q = {text}.",
        " ".join(str(v) for v in column) + "  (Q column, rows in table order)",
        working,
        answer_lines=0,
        table=((*names, "Q"), *rows),
        kind=kind,
        size=_ops_count(text),
    )


def _logic_question(lesson: str) -> QuestionMaker:
    def make(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
        return _truth_table_question(rng, _logic_shapes(lesson, d)[tier], s, d, lesson)

    return make


def _logic_ranges(lesson: str) -> Callable[[Difficulty], Ranges]:
    def ranges(d: Difficulty) -> Ranges:
        a, b, c = ((sh.gates + sh.nots,) * 2 for sh in _logic_shapes(lesson, d))
        return a, b, c

    return ranges


def _logic_hints(lesson: str) -> Callable[[Difficulty], tuple[str, str, str]]:
    def hints(d: Difficulty) -> tuple[str, str, str]:
        def text(sh: _Shape) -> str:
            nots = {0: "no NOT", 1: "one NOT"}.get(sh.nots, f"{sh.nots} NOTs")
            return f"{sh.inputs} inputs, {nots}"

        a, b, c = (text(sh) for sh in _logic_shapes(lesson, d))
        return a, b, c

    return hints


GATE_RULES = {
    "AND": "AND is 1 only when both inputs are 1",
    "OR": "OR is 1 when either input is 1, or both",
    "XOR": "XOR is 1 when exactly one input is 1",
    "NAND": "NAND is NOT AND: 0 only when both inputs are 1",
    "NOR": "NOR is NOT OR: 1 only when both inputs are 0",
}


def _logic_example(lesson: str) -> ExampleMaker:
    def make(rng: random.Random, d: Difficulty, s: Settings) -> Example:
        shape = _logic_shapes(lesson, d)[1]
        ops = [o for o in _ops_for(s, d) if o not in BEYOND_GCSE_GATES] or _ops_for(s, d)
        names = _names(rng, shape)
        envs = _envs(names)
        expr, inner = _shaped(rng, shape, ops, names)
        for _ in range(300):
            expr, inner = _shaped(rng, shape, ops, names)
            if not _degenerate(expr, names, _columns(expr, envs)):
                break
        text = _strip(expr.text)
        used = [op for op in ("AND", "OR", "XOR", "NAND", "NOR") if f" {op} " in f" {text} "]
        steps = [f"{GATE_RULES[op]}." for op in used]
        if "NOT" in text.split():
            steps.append("NOT turns 0 into 1 and 1 into 0.")
        steps.append(
            f"List every combination of {', '.join(names)} in binary order"
            f" ({2 ** len(names)} rows), then work out Q for each row."
        )
        column = _columns(expr, envs)
        heads = [_strip(x.text) for x in inner]
        rows = tuple(
            (
                *(str(env[n]) for n in names),
                *(str(x.fn(env)) for x in inner),
                str(q),
            )
            for env, q in zip(envs, column, strict=True)
        )
        if inner:
            steps.append("Work out the inside of each bracket in a column of its own first.")
        return Example(
            f"Complete the truth table for Q = {text}.",
            tuple(steps),
            "Q = " + " ".join(str(v) for v in column),
            ((*names, *heads, "Q"), *rows),
        )

    return make


def _simplify_steps(difficulty: Difficulty) -> tuple[int, int, int]:
    return {"easy": (1, 1, 2), "medium": (1, 2, 3), "hard": (2, 3, 3)}[difficulty]


def _simplify(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    return simplify_question(rng, _simplify_steps(d)[tier], s.laws, set())


def _simplify_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    q = simplify_question(rng, 2, s.laws, set())
    return Example(
        q.prompt,
        tuple(f"{step.text()}." for step in q.steps),
        q.answer,
    )


# ---------------------------------------------------------------- File sizes
def _units(board: str) -> tuple[int, str, str]:
    """Pearson Edexcel 1CP2 (2.3.1) measures in binary multiples (kibibyte, mebibyte);
    OCR J277 (1.2.3) and AQA 8525 (3.3.3) in 1000s."""
    return (1024, "KiB", "MiB") if board == "edexcel" else (1000, "KB", "MB")


def _num(x: float) -> str:
    return f"{x:,.0f}" if x == int(x) else f"{x:,.2f}"


def _size_answer(bits: int, tier: int, s: Settings) -> tuple[str, str]:
    """The answer at the tier's unit, and the working's last step."""
    k, kb, mb = _units(s.board)
    nbytes = bits / 8
    if tier == 0:
        return f"{_num(nbytes)} bytes", f"{bits:,} bits ÷ 8 = {_num(nbytes)} bytes"
    if tier == 1:
        return (
            f"{_num(nbytes / k)} {kb}",
            f"{bits:,} bits ÷ 8 = {_num(nbytes)} bytes; ÷ {k:,} = {_num(nbytes / k)} {kb}",
        )
    return (
        f"{_num(nbytes / k / k)} {mb}",
        f"{bits:,} bits ÷ 8 = {_num(nbytes)} bytes; ÷ {k:,} ÷ {k:,} = {_num(nbytes / k / k)} {mb}",
    )


def _unit_phrase(tier: int, s: Settings) -> str:
    k, kb, mb = _units(s.board)
    if tier == 0:
        return "in bytes"
    unit = kb if tier == 1 else mb
    scale = f"1 {kb} = {k:,} bytes" + (f", 1 {mb} = {k:,} {kb}" if tier == 2 else "")
    return f"in {unit} ({scale}), to 2 decimal places"


IMAGE_SIZES: tuple[tuple[tuple[int, int], ...], ...] = (
    ((8, 8), (8, 16), (16, 16), (16, 8), (24, 16), (32, 16), (32, 32)),
    ((100, 100), (128, 128), (200, 150), (256, 256), (320, 240), (400, 300)),
    ((640, 480), (800, 600), (1024, 768), (1280, 720), (1920, 1080)),
)
IMAGE_DEPTHS: dict[Difficulty, tuple[tuple[int, ...], ...]] = {
    "easy": ((1,), (1, 8), (8,)),
    "medium": ((1, 2), (1, 4, 8), (8, 16, 24)),
    "hard": ((1, 2, 4), (4, 8, 16), (16, 24, 32)),
}


def _image_ranges(d: Difficulty) -> Ranges:
    out = []
    for tier in range(3):
        sizes = [w * h for w, h in IMAGE_SIZES[tier]]
        depths = IMAGE_DEPTHS[d][tier]
        out.append((min(sizes) * min(depths), max(sizes) * max(depths)))
    return out[0], out[1], out[2]


def _image(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    w, h = rng.choice(IMAGE_SIZES[tier])
    depth = rng.choice(IMAGE_DEPTHS[d][tier])
    bits = w * h * depth
    answer, last = _size_answer(bits, tier, s)
    return Question(
        f"An image is {w} × {h} pixels with a colour depth of {depth} "
        f"bit{'s' if depth > 1 else ''}. Calculate its file size {_unit_phrase(tier, s)}.",
        answer,
        f"{w} × {h} × {depth} = {bits:,} bits; {last}",
        answer_lines=2,
        kind="image",
        size=bits,
    )


def _image_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    w, h = rng.choice(IMAGE_SIZES[1])
    depth = 8
    bits = w * h * depth
    answer, last = _size_answer(bits, 1, s)
    return Example(
        f"An image is {w} × {h} pixels with a colour depth of {depth} bits. "
        f"Calculate its file size {_unit_phrase(1, s)}.",
        (
            "File size (bits) = width × height × colour depth.",
            f"{w} × {h} = {w * h:,} pixels; × {depth} bits = {bits:,} bits.",
            last[len(f"{bits:,} bits ") :].capitalize().replace("÷", "Divide by", 1) + ".",
        ),
        answer,
    )


SOUND: dict[Difficulty, tuple[tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]], ...]] = {
    # (sample rates, resolutions, seconds) for each section
    "easy": (
        ((8000,), (8,), (1, 2, 5)),
        ((8000, 11025), (8,), (5, 10)),
        ((22050,), (8, 16), (10, 30)),
    ),
    "medium": (
        ((8000,), (8,), (1, 2, 5)),
        ((8000, 11025, 22050), (8, 16), (5, 10, 30)),
        ((44100, 48000), (16, 24), (30, 60, 180)),
    ),
    "hard": (
        ((8000, 11025), (8, 16), (2, 5, 10)),
        ((22050, 44100), (16,), (10, 30, 60)),
        ((44100, 48000, 96000), (16, 24), (60, 180, 300)),
    ),
}


def _sound_ranges(d: Difficulty) -> Ranges:
    out = []
    for rates, res, secs in SOUND[d]:
        out.append((min(rates) * min(res) * min(secs), max(rates) * max(res) * max(secs)))
    return out[0], out[1], out[2]


def _sound(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    rates, resolutions, seconds = SOUND[d][tier]
    rate, res, secs = rng.choice(rates), rng.choice(resolutions), rng.choice(seconds)
    bits = rate * res * secs
    answer, last = _size_answer(bits, tier, s)
    return Question(
        f"A sound is sampled at {rate:,} Hz with a sample resolution of {res} bits for "
        f"{secs} second{'s' if secs > 1 else ''}. Calculate its file size {_unit_phrase(tier, s)}.",
        answer,
        f"{rate:,} × {res} × {secs} = {bits:,} bits; {last}",
        answer_lines=2,
        kind="sound",
        size=bits,
    )


def _sound_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    rate, res, secs = 8000, 8, rng.choice((10, 20, 30))
    bits = rate * res * secs
    answer, last = _size_answer(bits, 1, s)
    return Example(
        f"A sound is sampled at {rate:,} Hz with a sample resolution of {res} bits for "
        f"{secs} seconds. Calculate its file size {_unit_phrase(1, s)}.",
        (
            "File size (bits) = sample rate × resolution × seconds.",
            f"{rate:,} × {res} × {secs} = {bits:,} bits.",
            last[len(f"{bits:,} bits ") :].capitalize().replace("÷", "Divide by", 1) + ".",
        ),
        answer,
    )


TEXT: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...] = (
    ((10, 20, 25, 40, 50, 64), (8,)),
    ((120, 200, 360, 480, 800, 1000), (7, 8)),
    ((2000, 4000, 5000, 8000, 10000), (16,)),
)


def _text_ranges(d: Difficulty) -> Ranges:
    out = [(min(c) * min(b), max(c) * max(b)) for c, b in TEXT]
    return out[0], out[1], out[2]


def _text(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    chars_options, per_options = TEXT[tier]
    chars, per = rng.choice(chars_options), rng.choice(per_options)
    bits = chars * per
    # A text file is small: bytes until the stretch, then KB, never MB.
    answer, last = _size_answer(bits, max(tier - 1, 0), s)
    code = {7: "7-bit ASCII", 8: "8-bit ASCII", 16: "16-bit Unicode"}[per]
    phrase = _unit_phrase(max(tier - 1, 0), s)
    return Question(
        f"A text file holds {chars:,} characters in {code} ({per} bits per character). "
        f"Calculate its size {phrase}.",
        answer,
        f"{chars:,} × {per} = {bits:,} bits; {last}",
        answer_lines=2 if tier else 1,
        kind="text",
        size=bits,
    )


def _text_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    chars = rng.choice((150, 300, 600))
    bits = chars * 8
    answer, _last = _size_answer(bits, 0, s)
    return Example(
        f"A text file holds {chars} characters in 8-bit ASCII (8 bits per character). "
        "Calculate its size in bytes.",
        (
            "File size (bits) = bits per character × number of characters.",
            f"8 × {chars} = {bits:,} bits.",
            "Divide by 8 for bytes (here that just undoes the 8 bits per character).",
        ),
        answer,
    )


# ---------------------------------------------------------------- Compression
def _rle_ranges(d: Difficulty) -> Ranges:
    """The number of runs."""
    return {
        "easy": ((3, 3), (4, 5), (5, 6)),
        "medium": ((3, 4), (5, 6), (7, 8)),
        "hard": ((4, 5), (6, 8), (8, 10)),
    }[d]


def _rle_text(rng: random.Random, d: Difficulty, tier: int) -> str:
    runs = _pick(rng, _rle_ranges(d)[tier])
    alphabet = ("AB", "ABC", "ABCW")[tier]
    longest = (5, 7, 12)[tier]  # the stretch has runs of 10 or more: two-digit counts
    text, last = "", ""
    for _ in range(runs):
        ch = rng.choice([c for c in alphabet if c != last])
        text += ch * rng.randint(1, longest)
        last = ch
    return text


def _rle_runs(text: str) -> int:
    return len(rle_encode(text).split())


def _rle_enc(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    text = _rle_text(rng, d, tier)
    return Question(
        f"Run-length encode: {text}",
        rle_encode(text),
        f"{len(text)} characters in {_rle_runs(text)} runs",
        kind="rle_enc",
        size=_rle_runs(text),
    )


def _rle_dec(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    text = _rle_text(rng, d, tier)
    return Question(
        f"Decode the run-length encoding: {rle_encode(text)}",
        text,
        f"{_rle_runs(text)} runs, {len(text)} characters",
        kind="rle_dec",
        size=_rle_runs(text),
    )


def _rle_example(decode: bool) -> ExampleMaker:
    def make(rng: random.Random, d: Difficulty, s: Settings) -> Example:
        text = "".join(ch * n for ch, n in zip("WBWB", rng.sample(range(2, 7), 4), strict=True))
        code = rle_encode(text)
        runs = code.split()
        table = (
            ("Run", *(str(i) for i in range(1, len(runs) + 1))),
            ("Count", *(r[:-1] for r in runs)),
            ("Character", *(r[-1] for r in runs)),
        )
        if decode:
            return Example(
                f"Decode the run-length encoding: {code}",
                (
                    "Each pair is a count, then the character it repeats.",
                    "Write each character that many times, in order.",
                ),
                text,
                table,
            )
        return Example(
            f"Run-length encode: {text}",
            (
                "Split the data into runs: groups of the same character in a row.",
                "Write each run as its length, then the character.",
                f"{len(text)} characters become {len(runs)} pairs.",
            ),
            code,
            table,
        )

    return make


def _huffman_ranges(d: Difficulty) -> Ranges:
    """The number of symbols."""
    return {
        "easy": ((3, 3), (3, 4), (4, 5)),
        "medium": ((3, 3), (4, 4), (5, 6)),
        "hard": ((4, 4), (5, 5), (6, 6)),
    }[d]


def huffman_merges(freqs: Mapping[str, int]) -> list[tuple[int, int]]:
    """The two weights merged at each step, lightest first."""
    heap = list(freqs.values())
    heapq.heapify(heap)
    merges = []
    while len(heap) > 1:
        a, b = heapq.heappop(heap), heapq.heappop(heap)
        merges.append((a, b))
        heapq.heappush(heap, a + b)
    return merges


def _merge_text(merges: list[tuple[int, int]]) -> str:
    return "; ".join(f"{a} + {b} = {a + b}" for a, b in merges)


def _huffman(rng: random.Random, d: Difficulty, tier: int, s: Settings) -> Question:
    n = _pick(rng, _huffman_ranges(d)[tier])
    letters = rng.sample("ABCDEFGH", n)
    freqs = {ch: rng.randint(1, 12) for ch in letters}
    merges = huffman_merges(freqs)
    bits = sum(a + b for a, b in merges)
    table = ", ".join(f"{ch}: {f}" for ch, f in freqs.items())
    prompt = (
        f"Build a Huffman tree for the frequencies {table}. "
        "How many bits does the compressed message use?"
    )
    answer = f"{bits} bits"
    if tier == 2:
        chars = sum(freqs.values())
        prompt += " How many bits does that save over 8-bit ASCII?"
        answer += f"; ASCII needs {chars} × 8 = {chars * 8} bits, a saving of {chars * 8 - bits}"
    return Question(
        prompt,
        answer,
        f"Merges: {_merge_text(merges)}. Total = sum of the merged weights = {bits}",
        answer_lines=3,
        kind="huffman",
        size=n,
    )


def _huffman_example(rng: random.Random, d: Difficulty, s: Settings) -> Example:
    letters = rng.sample("ABCDEFGH", 4)
    freqs = {
        ch: f
        for ch, f in zip(letters, sorted(rng.sample(range(1, 10), 4), reverse=True), strict=True)
    }
    merges = huffman_merges(freqs)
    bits = sum(a + b for a, b in merges)
    table = ", ".join(f"{ch}: {f}" for ch, f in freqs.items())
    rows = tuple((str(i), f"{a} + {b}", str(a + b)) for i, (a, b) in enumerate(merges, 1))
    return Example(
        f"Build a Huffman tree for the frequencies {table}. "
        "How many bits does the compressed message use?",
        (
            "Take the two smallest weights, join them under a new node, and put the new "
            "node back in the list. Repeat until one node is left.",
            "Each character's code is its path from the root (0 left, 1 right): the "
            "deeper it sits, the more bits it costs.",
            f"Total bits = each frequency × its code length = the sum of the merged weights "
            f"= {' + '.join(str(a + b) for a, b in merges)} = {bits}.",
        ),
        f"{bits} bits",
        (("Step", "Merge", "New node"), *rows),
    )


# ---------------------------------------------------------------- the catalogue
def _on(**codes: str) -> dict[str, str]:
    """The spec point on each board that has the skill (boards left out do not)."""
    return codes


def _review(
    unit: str, slug: str, title: str, what: str, legacy: str, covers: str, **kw: object
) -> Lesson:
    """``covers``: the slugs of the lessons the old sheet mixes, space-separated."""
    return Lesson(unit, slug, title, what, legacy=legacy, covers=tuple(covers.split()), **kw)  # type: ignore[arg-type]


UNITS: tuple[Unit, ...] = (
    Unit(
        "binary",
        "Binary & hex",
        (
            Lesson(
                "binary",
                "denary-to-binary",
                "Denary to binary",
                "Place-value table, 8 bits",
                _on(ocr="1.2.4", aqa="3.3.2", edexcel="2.1.3"),
                aim="Convert a denary number to 8-bit binary using a place-value table.",
                kinds=("d2b",),
                ranges=_number_ranges,
                hints=_number_hints,
                question=_d2b,
                example=_d2b_example,
            ),
            Lesson(
                "binary",
                "binary-to-denary",
                "Binary to denary",
                "Add the place values that hold a 1",
                _on(ocr="1.2.4", aqa="3.3.2", edexcel="2.1.3"),
                aim="Convert an 8-bit binary number to denary by adding place values.",
                kinds=("b2d",),
                ranges=_number_ranges,
                hints=_number_hints,
                question=_b2d,
                example=_b2d_example,
            ),
            Lesson(
                "binary",
                "binary-and-hex",
                "Binary and hex",
                "Nibbles to hex digits, both ways",
                _on(ocr="1.2.4", aqa="3.3.2", edexcel="2.1.6"),
                aim="Convert between binary and hexadecimal one nibble at a time.",
                kinds=("b2h", "h2b"),
                ranges=_hex_ranges,
                hints=_hex_hints,
                question=_bin_hex,
                example=_bin_hex_example,
            ),
            Lesson(
                "binary",
                "denary-and-hex",
                "Denary and hex",
                "Sixteens and ones, both ways",
                # Edexcel 2.1.6 converts hex to and from binary only.
                _on(ocr="1.2.4", aqa="3.3.2"),
                aim="Convert between denary and hexadecimal by counting sixteens and ones.",
                kinds=("d2h", "h2d"),
                ranges=_hex_ranges,
                hints=_hex_hints,
                question=_den_hex,
                example=_den_hex_example,
            ),
            _review(
                "binary",
                "review",
                "Review",
                "All conversions mixed",
                "binary",
                "denary-to-binary binary-to-denary binary-and-hex denary-and-hex",
            ),
        ),
    ),
    Unit(
        "arithmetic",
        "Binary arithmetic",
        (
            Lesson(
                "arithmetic",
                "addition",
                "Binary addition",
                "Two 8-bit numbers, carries shown",
                _on(ocr="1.2.4", aqa="3.3.4", edexcel="2.1.4"),
                aim="Add two 8-bit binary numbers, carrying from column to column.",
                kinds=("add",),
                ranges=_number_ranges,
                hints=lambda d: _range_hints(_number_ranges(d), ""),
                question=_addition,
                example=_addition_example,
            ),
            Lesson(
                "arithmetic",
                "overflow",
                "Overflow",
                "Spot and explain overflow in 8 bits",
                # AQA 3.3.4: answers never carry beyond the 8th bit.
                _on(ocr="1.2.4", edexcel="2.1.5"),
                aim="Add two 8-bit numbers and decide whether the result overflows.",
                kinds=("overflow",),
                ranges=_overflow_ranges,
                hints=lambda d: ("totals near 255", "some overflow", "all overflow"),
                question=_overflow,
                example=_overflow_example,
            ),
            Lesson(
                "arithmetic",
                "logical-shifts",
                "Logical shifts",
                "Shift left or right; effect on the value",
                _on(ocr="1.2.4", aqa="3.3.4", edexcel="2.1.4"),
                aim="Apply a logical shift and say what it does to the value.",
                kinds=("lshift",),
                ranges=_shift_ranges,
                hints=_shift_hints,
                question=_logical_shift,
                example=_logical_shift_example,
            ),
            Lesson(
                "arithmetic",
                "arithmetic-shifts",
                "Arithmetic shifts",
                "Right shift that keeps the sign",
                # OCR shifts are logical only; AQA 3.3.4 says only a logical shift.
                _on(edexcel="2.1.4"),
                aim="Apply an arithmetic shift right to a two's complement number.",
                kinds=("ashift",),
                ranges=_shift_ranges,
                hints=lambda d: ("positive numbers", "negative numbers", "further, negative"),
                question=_arithmetic_shift,
                example=_arithmetic_shift_example,
            ),
            _review(
                "arithmetic",
                "review-addition",
                "Review: addition",
                "Addition and overflow mixed",
                "binary_addition",
                "addition overflow",
            ),
            _review(
                "arithmetic",
                "review-shifts",
                "Review: shifts",
                "Logical and arithmetic, left and right",
                "shifts",
                "logical-shifts arithmetic-shifts",
            ),
        ),
    ),
    Unit(
        "twos-complement",
        "Two's complement",
        (
            Lesson(
                "twos-complement",
                "to-twos-complement",
                "Denary to two's complement",
                "Flip and add 1, 8 bits",
                # OCR J277 and AQA 8525 have no negative numbers.
                _on(edexcel="2.1.3"),
                aim="Write a negative denary number in 8-bit two's complement.",
                kinds=("to_tc",),
                ranges=_tc_ranges,
                hints=_tc_hints,
                question=_to_tc,
                example=_to_tc_example,
            ),
            Lesson(
                "twos-complement",
                "from-twos-complement",
                "Two's complement to denary",
                "The sign bit is worth -128",
                _on(edexcel="2.1.3"),
                aim="Read an 8-bit two's complement number as denary.",
                kinds=("from_tc",),
                ranges=_tc_ranges,
                hints=_tc_hints,
                question=_from_tc,
                example=_from_tc_example,
            ),
            _review(
                "twos-complement",
                "review",
                "Review",
                "Both directions mixed",
                "twos_complement",
                "to-twos-complement from-twos-complement",
            ),
        ),
    ),
    Unit(
        "logic",
        "Logic",
        (
            *(
                Lesson(
                    "logic",
                    slug,
                    title,
                    what,
                    _on(ocr="2.4.1", aqa="3.4.2", edexcel="1.3.1"),
                    aim=aim,
                    kinds=(slug,),
                    ranges=_logic_ranges(slug),
                    hints=_logic_hints(slug),
                    question=_logic_question(slug),
                    example=_logic_example(slug),
                    uses=("level",),
                )
                for slug, title, what, aim in (
                    (
                        "one-gate",
                        "One gate",
                        "One gate on two inputs",
                        "Complete the truth table for one logic gate.",
                    ),
                    (
                        "two-gates",
                        "Two gates",
                        "(A AND B) OR C, three inputs",
                        "Complete a truth table for two gates on three inputs.",
                    ),
                    (
                        "three-gates",
                        "Three gates",
                        "Brackets, and NOT over a bracket",
                        "Complete a truth table for three gates, inside the brackets first.",
                    ),
                )
            ),
            Lesson(
                "logic",
                "simplification",
                "Simplification",
                "Boolean laws, one family per sheet",
                {},  # A level on every board: no GCSE asks for Boolean algebra
                aim="Simplify a Boolean expression, naming the law used at each step.",
                kinds=("simplify",),
                ranges=lambda d: tuple((n, n) for n in _simplify_steps(d)),  # type: ignore[arg-type,return-value]
                hints=lambda d: tuple(  # type: ignore[arg-type,return-value]
                    f"{n} step" + ("s" if n > 1 else "") for n in _simplify_steps(d)
                ),
                question=_simplify,
                example=_simplify_example,
                uses=("laws",),
            ),
            _review(
                "logic",
                "review-truth-tables",
                "Review: truth tables",
                "Shape set by difficulty",
                "truth_tables",
                "one-gate two-gates three-gates",
                uses=("level",),
            ),
            _review(
                "logic",
                "review-simplification",
                "Review: simplification",
                "Steps set by difficulty",
                "boolean_simplification",
                "simplification",
                uses=("laws",),
            ),
        ),
    ),
    Unit(
        "file-sizes",
        "File sizes",
        (
            Lesson(
                "file-sizes",
                "image",
                "Image file size",
                "Width × height × colour depth",
                _on(ocr="1.2.3", aqa="3.3.6", edexcel="2.3.1"),
                aim="Calculate the file size of a bitmap image.",
                kinds=("image",),
                ranges=_image_ranges,
                hints=lambda d: ("in bytes", "in kilobytes", "in megabytes"),
                question=_image,
                example=_image_example,
            ),
            Lesson(
                "file-sizes",
                "sound",
                "Sound file size",
                "Sample rate × resolution × seconds",
                _on(ocr="1.2.3", aqa="3.3.7", edexcel="2.3.1"),
                aim="Calculate the file size of a sampled sound.",
                kinds=("sound",),
                ranges=_sound_ranges,
                hints=lambda d: ("in bytes", "in kilobytes", "in megabytes"),
                question=_sound,
                example=_sound_example,
            ),
            Lesson(
                "file-sizes",
                "text",
                "Text file size",
                "Characters × bits per character",
                # AQA 3.3.8: the bits to store uncompressed data in ASCII.
                _on(ocr="1.2.3", aqa="3.3.8", edexcel="2.3.1"),
                aim="Calculate the size of a text file from its characters and encoding.",
                kinds=("text",),
                ranges=_text_ranges,
                hints=lambda d: (
                    "8-bit ASCII, bytes",
                    "7- or 8-bit ASCII, bytes",
                    "16-bit Unicode, kilobytes",
                ),
                question=_text,
                example=_text_example,
            ),
            _review(
                "file-sizes",
                "review",
                "Review",
                "Images, sound and text mixed",
                "file_size",
                "image sound text",
            ),
        ),
    ),
    Unit(
        "compression",
        "Compression",
        (
            Lesson(
                "compression",
                "rle-encode",
                "RLE: encode",
                "Write the runs as count and character",
                # OCR 1.2.5 leaves out carrying out compression algorithms; Edexcel
                # 2.3.2 asks for lossless and lossy, naming no method.
                _on(aqa="3.3.8"),
                aim="Compress data with run-length encoding.",
                kinds=("rle_enc",),
                ranges=_rle_ranges,
                hints=lambda d: ("two letters", "three letters", "long runs"),
                question=_rle_enc,
                example=_rle_example(decode=False),
            ),
            Lesson(
                "compression",
                "rle-decode",
                "RLE: decode",
                "Expand the runs",
                _on(aqa="3.3.8"),
                aim="Expand run-length encoded data back to the original.",
                kinds=("rle_dec",),
                ranges=_rle_ranges,
                hints=lambda d: ("two letters", "three letters", "long runs"),
                question=_rle_dec,
                example=_rle_example(decode=True),
            ),
            Lesson(
                "compression",
                "huffman",
                "Huffman coding",
                "Total bits from a frequency table",
                _on(aqa="3.3.8"),
                aim="Build a Huffman tree and count the bits it uses.",
                kinds=("huffman",),
                ranges=_huffman_ranges,
                hints=lambda d: tuple(  # type: ignore[arg-type,return-value]
                    f"{lo} symbols" if lo == hi else f"{lo} or {hi} symbols"
                    for lo, hi in _huffman_ranges(d)
                ),
                question=_huffman,
                example=_huffman_example,
            ),
            _review(
                "compression",
                "review-rle",
                "Review: RLE",
                "Encode and decode mixed",
                "rle",
                "rle-encode rle-decode",
            ),
            _review(
                "compression",
                "review-huffman",
                "Review: Huffman",
                "Total bits",
                "huffman",
                "huffman",
            ),
        ),
    ),
)

LESSONS: dict[str, Lesson] = {lesson.key: lesson for unit in UNITS for lesson in unit.lessons}
UNIT_BY_SLUG: dict[str, Unit] = {unit.slug: unit for unit in UNITS}
#: Each old topic name and the Review lesson that makes its sheet.
LEGACY: dict[str, Lesson] = {lesson.legacy: lesson for lesson in LESSONS.values() if lesson.review}
DEFAULT_LESSON = "binary/denary-to-binary"

#: Where each board's spec points were checked (#75).
SPEC_SOURCES: dict[str, str] = {
    "ocr": "OCR GCSE (9-1) Computer Science J277 specification, Version 3.1 (May 2026)",
    "aqa": "AQA GCSE Computer Science 8525 specification, first teaching September 2025",
    "edexcel": "Pearson Edexcel GCSE (9-1) Computer Science 1CP2 specification, Issue 1 (2020)",
}


def unit_default(unit: Unit) -> Lesson:
    """The lesson a unit makes when none is named: its first Review, so an old
    command makes the sheet it always made, or its first lesson if it has none."""
    return next((lesson for lesson in unit.lessons if lesson.review), unit.lessons[0])


def resolve(name: str, lesson: str | None = None) -> Lesson:
    """A lesson from what a teacher types: ``binary`` (a unit: its Review),
    ``binary --lesson denary-to-binary``, ``binary/denary-to-binary``, or an old
    topic name (``shifts``, ``file_size``: that topic's Review). ValueError names
    the choices when nothing matches."""
    name = name.strip().lower()
    if "/" in name and lesson is None:
        name, lesson = name.split("/", 1)
    unit = UNIT_BY_SLUG.get(name) or UNIT_BY_SLUG.get(name.replace("_", "-"))
    if unit is None and name in LEGACY:
        if lesson is None:
            return LEGACY[name]
        unit = UNIT_BY_SLUG[LEGACY[name].unit]
    if unit is None:
        msg = f"unknown unit {name!r}; choose from {', '.join(UNIT_BY_SLUG)}"
        raise ValueError(msg)
    if lesson is None:
        return unit_default(unit)
    key = f"{unit.slug}/{lesson.strip().lower()}"
    if key not in LESSONS:
        choices = ", ".join(lesson.slug for lesson in unit.lessons)
        msg = f"unknown lesson {lesson!r} in {unit.slug}; choose from {choices}"
        raise ValueError(msg)
    return LESSONS[key]


def boards_of(lesson: Lesson) -> list[str]:
    """The boards a lesson is on. A Review is on the boards of the lessons it mixes, so
    a Review no GCSE board has (two's complement on OCR) greys too."""
    if not lesson.review:
        return list(lesson.spec)
    boards: list[str] = []
    for slug in lesson.covers:
        boards += [b for b in LESSONS[f"{lesson.unit}/{slug}"].spec if b not in boards]
    return boards


def on_board(lesson: Lesson, board: str) -> bool:
    return board in boards_of(lesson)


def spec_line(lesson: Lesson, board: str, names: Mapping[str, str]) -> str:
    """What a sheet's header says about the spec: the board's point, or where the
    lesson belongs when the board does not have it. ``names`` are the boards' names."""
    if board in lesson.spec:
        return f"{names.get(board, board)} {lesson.spec[board]}"
    others = [f"{names.get(b, b)} {code}" for b, code in lesson.spec.items()]
    if not others:
        return "Beyond GCSE (A level)"
    return f"Not on {names.get(board, board)} · on " + ", ".join(others)


def off_board_reason(lesson: Lesson, board: str, short: Mapping[str, str]) -> str:
    """One line for a greyed lesson: which boards have it."""
    if on_board(lesson, board):
        return ""
    boards = boards_of(lesson)
    if not boards:
        return "A level: not on any GCSE"
    return "On " + " and ".join(short.get(b, b) for b in boards) + " only"


def make_lesson(
    lesson: Lesson, seed: int, count: int, difficulty: Difficulty, settings: Settings
) -> LessonSheet:
    """The worked example, then ``count`` questions split over Warm-up, Practice and
    Stretch, each section's numbers drawn from its own range. A question the sheet
    already has is drawn again (a few times) so the sheet does not repeat itself."""
    if lesson.question is None or lesson.example is None or lesson.ranges is None:
        msg = f"{lesson.key} is a Review: make it with logic.generate({lesson.legacy!r})"
        raise ValueError(msg)
    rng = random.Random(seed)
    example = lesson.example(rng, difficulty, settings)
    seen = {example.question}
    hints = lesson.hints(difficulty) if lesson.hints else ("", "", "")
    parts: list[Part] = []
    for tier, (name, n) in enumerate(zip(SECTIONS, _split(count), strict=True)):
        questions: list[Question] = []
        for _ in range(n):
            q = lesson.question(rng, difficulty, tier, settings)
            for _retry in range(40):
                if q.prompt not in seen:
                    break
                q = lesson.question(rng, difficulty, tier, settings)
            seen.add(q.prompt)
            questions.append(q)
        if questions:
            parts.append(Part(name, hints[tier], tuple(questions)))
    return LessonSheet(lesson.aim, example, tuple(parts))


def lesson_note(lesson: Lesson, settings: Settings, difficulty: Difficulty) -> str:
    """What the header states beyond seed and difficulty: the gates or the laws."""
    if "level" in lesson.uses:
        gates = ", ".join(gate_set(settings.board, settings.level, difficulty))
        prefix = "A-level · " if settings.level == "a_level" else ""
        return f"{prefix}gates: {gates}"
    if "laws" in lesson.uses:
        return "laws: " + ", ".join(LAW_FAMILIES[settings.laws])
    return ""
