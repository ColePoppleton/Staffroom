"""Pure question generators. Each is ``(seed, count, difficulty) -> list[Question]``
and is deterministic for a seed, so a sheet can be regenerated from the
seed printed on it. Answers are checked by independent computation in the
tests (``int(x, 2)`` and friends), never by the generator's own arithmetic.
"""

from __future__ import annotations

import heapq
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

Difficulty = Literal["easy", "medium", "hard"]


@dataclass(frozen=True)
class Question:
    prompt: str
    answer: str
    working: str = ""  # shown in the key
    answer_lines: int = 1
    table: tuple[tuple[str, ...], ...] | None = None  # columns + rows for the sheet


Generator = Callable[[int, int, Difficulty], list[Question]]


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
    count: int = field(default=10, metadata={"label": "Questions", "min": 1, "max": 60})
    seed: int = field(default=42, metadata={"label": "Seed", "min": 0, "max": 999_999})
    difficulty: Difficulty = field(default="medium", metadata={"label": "Difficulty"})
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


@dataclass(frozen=True)
class Expr:
    text: str
    fn: Callable[[dict[str, int]], int]


def _leaf(name: str, negate: bool) -> Expr:
    def fn(env: dict[str, int]) -> int:
        return 1 - env[name] if negate else env[name]

    return Expr(f"NOT {name}" if negate else name, fn)


def _node(op: str, left: Expr, right: Expr) -> Expr:
    apply = _OPS[op]

    def fn(env: dict[str, int]) -> int:
        return apply(left.fn(env), right.fn(env))

    return Expr(f"({left.text} {op} {right.text})", fn)


def _random_expr(rng: random.Random, inputs: list[str], depth: int) -> Expr:
    if depth == 0 or (depth < 2 and rng.random() < 0.3):
        return _leaf(rng.choice(inputs), rng.random() < 0.3)
    op = rng.choice(list(_OPS))
    return _node(op, _random_expr(rng, inputs, depth - 1), _random_expr(rng, inputs, depth - 1))


def truth_tables(seed: int, count: int, difficulty: Difficulty) -> list[Question]:
    rng = random.Random(seed)
    n_inputs = 2 if difficulty == "easy" else 3
    depth = 1 if difficulty == "easy" else 2
    names = ["A", "B", "C"][:n_inputs]
    out: list[Question] = []
    for _ in range(count):
        expr = _random_expr(rng, names, depth)
        if expr.text in names or expr.text.startswith("NOT "):
            expr = _random_expr(rng, names, 1)
        text = (
            expr.text[1:-1] if expr.text.startswith("(") and expr.text.endswith(")") else expr.text
        )
        rows: list[tuple[str, ...]] = []
        answers: list[str] = []
        for combo in range(2**n_inputs):
            env = {name: (combo >> (n_inputs - 1 - i)) & 1 for i, name in enumerate(names)}
            value = expr.fn(env)
            rows.append((*(str(env[n]) for n in names), ""))
            answers.append(str(value))
        out.append(
            Question(
                f"Complete the truth table for Q = {text}.",
                " ".join(answers) + "  (Q column, rows in table order)",
                "",
                answer_lines=0,
                table=((*names, "Q"), *rows),
            )
        )
    return out


# ---------------------------------------------------------------- 6. Boolean simplification
_LAWS: list[tuple[str, Callable[[str], str], str]] = [
    ("identity", lambda a: f"({a} AND 1)", "A AND 1 = A"),
    ("identity", lambda a: f"({a} OR 0)", "A OR 0 = A"),
    ("idempotent", lambda a: f"({a} AND {a})", "A AND A = A"),
    ("idempotent", lambda a: f"({a} OR {a})", "A OR A = A"),
    ("double negation", lambda a: f"NOT NOT {a}", "NOT NOT A = A"),
    ("absorption", lambda a: f"({a} OR ({a} AND B))", "A OR (A AND B) = A"),
    ("absorption", lambda a: f"({a} AND ({a} OR B))", "A AND (A OR B) = A"),
    ("complement", lambda a: f"(({a} OR NOT {a}) AND {a})", "A OR NOT A = 1, then 1 AND A = A"),
]


def boolean_simplification(seed: int, count: int, difficulty: Difficulty) -> list[Question]:
    """Start from a simple target and wrap it in identities; the key lists
    the laws in reverse, which is the simplification."""
    rng = random.Random(seed)
    steps_n = {"easy": 1, "medium": 2, "hard": 3}[difficulty]
    out: list[Question] = []
    for _ in range(count):
        target = rng.choice(["A", "B", "C", "(A AND B)", "(A OR B)", "NOT A"])
        expr = target
        applied: list[str] = []
        for _ in range(steps_n):
            name, wrap, law = rng.choice(_LAWS)
            expr = wrap(expr)
            applied.append(f"{name}: {law}")
        shown = expr[1:-1] if expr.startswith("(") and expr.endswith(")") else expr
        working = "\n".join(f"{i}. {law}" for i, law in enumerate(reversed(applied), 1))
        out.append(
            Question(
                f"Simplify: {shown}",
                target.strip("()"),
                working,
                answer_lines=2 + steps_n,
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


def generate(topic: str, seed: int, count: int, difficulty: Difficulty) -> list[Question]:
    try:
        gen = GENERATORS[topic]
    except KeyError:
        msg = f"unknown topic {topic!r}; choose from {', '.join(GENERATORS)}"
        raise ValueError(msg) from None
    return gen(seed, count, difficulty)
