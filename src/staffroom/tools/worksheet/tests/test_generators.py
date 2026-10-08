"""Every generator's answers are verified by independent computation."""

import heapq
import itertools
import re
from collections.abc import Callable

import pytest

from staffroom.tools.worksheet import logic

DIFFS = ["easy", "medium", "hard"]
SEEDS = [1, 7, 42, 1234]


def digits(s: str) -> str:
    return s.replace(" ", "")


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("difficulty", DIFFS)
def test_binary(seed: int, difficulty: str) -> None:
    for q in logic.binary(seed, 20, difficulty):  # type: ignore[arg-type]
        p, a = q.prompt, q.answer
        if p.startswith("Convert") and "to binary (" in p:
            n = int(re.search(r"Convert (\d+)", p).group(1))  # type: ignore[union-attr]
            assert int(digits(a), 2) == n
        elif "to denary" in p and "(hex)" not in p:
            b = re.search(r"Convert ([01 ]+) to denary", p).group(1)  # type: ignore[union-attr]
            assert int(a) == int(digits(b), 2)
        elif "to hexadecimal" in p and "Convert" in p and re.search(r"Convert (\d+) to hex", p):
            n = int(re.search(r"Convert (\d+)", p).group(1))  # type: ignore[union-attr]
            assert int(a, 16) == n
        elif "(hex) to denary" in p:
            h = re.search(r"Convert ([0-9A-F]+) \(hex\)", p).group(1)  # type: ignore[union-attr]
            assert int(a) == int(h, 16)
        elif "(hex) to binary" in p:
            h = re.search(r"Convert ([0-9A-F]+) \(hex\)", p).group(1)  # type: ignore[union-attr]
            assert int(digits(a), 2) == int(h, 16)
        else:  # binary to hex
            b = re.search(r"Convert ([01 ]+) to hexadecimal", p).group(1)  # type: ignore[union-attr]
            assert int(a, 16) == int(digits(b), 2)


@pytest.mark.parametrize("seed", SEEDS)
def test_twos_complement(seed: int) -> None:
    for q in logic.twos_complement(seed, 30, "medium"):
        if q.prompt.startswith("Write"):
            n = int(re.search(r"Write (-?\d+)", q.prompt).group(1))  # type: ignore[union-attr]
            assert int(digits(q.answer), 2) == n % 256
        else:
            b = re.search(r"is ([01 ]+) \(", q.prompt).group(1)  # type: ignore[union-attr]
            v = int(digits(b), 2)
            assert int(q.answer) == (v - 256 if v >= 128 else v)


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("difficulty", DIFFS)
def test_binary_addition(seed: int, difficulty: str) -> None:
    qs = logic.binary_addition(seed, 20, difficulty)  # type: ignore[arg-type]
    for q in qs:
        a, b = re.search(r"Add ([01 ]+) and ([01 ]+) \(", q.prompt).groups()  # type: ignore[union-attr]
        total = int(digits(a), 2) + int(digits(b), 2)
        result, flag = q.answer.split(", overflow: ")
        assert int(digits(result), 2) == total % 256
        assert (flag == "yes") == (total > 255)
    if difficulty == "hard":
        assert all("overflow: yes" in q.answer for q in qs)


@pytest.mark.parametrize("seed", SEEDS)
def test_shifts(seed: int) -> None:
    for q in logic.shifts(seed, 30, "hard"):
        m = re.search(r"Apply a (\w+) shift (\w+) by (\d) to ([01 ]+)\.", q.prompt)
        assert m
        kind, direction, places, pattern = (
            m.group(1),
            m.group(2),
            int(m.group(3)),
            digits(m.group(4)),
        )
        n = int(pattern, 2)
        result = int(digits(q.answer.split(";")[0]), 2)
        if direction == "left":
            assert result == (n << places) & 0xFF
        elif kind == "logical":
            assert result == n >> places
        else:
            signed = n - 256 if n >= 128 else n
            assert result == (signed >> places) & 0xFF


@pytest.mark.parametrize("seed", SEEDS)
@pytest.mark.parametrize("difficulty", ["easy", "hard"])
def test_truth_tables(seed: int, difficulty: str) -> None:
    ops: dict[str, Callable[[bool, bool], bool]] = {
        "AND": lambda a, b: a and b,
        "OR": lambda a, b: a or b,
        "XOR": lambda a, b: a != b,
        "NAND": lambda a, b: not (a and b),
        "NOR": lambda a, b: not (a or b),
    }

    def evaluate(expr: str, env: dict[str, bool]) -> bool:
        # Independent evaluator: rewrite to Python and eval.
        py = expr
        for name in ops:
            py = re.sub(rf"\b{name}\b", f"__{name}__", py)
        py = py.replace("NOT ", " not ")
        tokens = re.split(r"(\(|\)|__\w+__|\bnot\b|\b[ABC]\b)", py)
        # Evaluate with a tiny recursive-descent parser over tokens.
        toks = [t.strip() for t in tokens if t.strip()]
        pos = 0

        def primary() -> bool:
            nonlocal pos
            t = toks[pos]
            pos += 1
            if t == "(":
                v = binary()
                assert toks[pos] == ")"
                pos += 1
                return v
            if t == "not":
                return not primary()
            return env[t]

        def binary() -> bool:
            nonlocal pos
            left = primary()
            while pos < len(toks) and toks[pos].startswith("__"):
                op = toks[pos].strip("_")
                pos += 1
                right = primary()
                left = bool(ops[op](left, right))
            return left

        return binary()

    for q in logic.truth_tables(seed, 15, difficulty):  # type: ignore[arg-type]
        assert q.table is not None
        expr = q.prompt.split("Q = ")[1].rstrip(".")
        names = list(q.table[0][:-1])
        answers = q.answer.split("  ")[0].split(" ")
        for row, expected in zip(q.table[1:], answers, strict=True):
            env = {n: v == "1" for n, v in zip(names, row[:-1], strict=True)}
            assert evaluate(expr, env) == (expected == "1"), (expr, env)


@pytest.mark.parametrize("seed", SEEDS)
def test_boolean_simplification_is_equivalent(seed: int) -> None:
    def truth(expr: str) -> list[bool]:
        py = expr.replace("AND", "and").replace("OR", "or").replace("NOT", "not")
        rows = []
        for a, b, c in itertools.product([False, True], repeat=3):
            rows.append(bool(eval(py, {}, {"A": a, "B": b, "C": c})))
        return rows

    for q in logic.boolean_simplification(seed, 20, "hard"):
        expr = q.prompt.removeprefix("Simplify: ")
        assert truth(expr) == truth(q.answer)
        assert q.working.count("\n") == 2  # three laws listed for hard


@pytest.mark.parametrize("seed", SEEDS)
def test_file_size(seed: int) -> None:
    for q in logic.file_size(seed, 30, "hard"):
        nums = [int(x) for x in re.findall(r"\d+", q.prompt.split(". ")[0].replace(",", ""))]
        answer_bytes = float(q.answer.split(" bytes")[0])
        if q.prompt.startswith("An image"):
            w, h, depth = nums[:3]
            assert answer_bytes == w * h * depth / 8
        elif q.prompt.startswith("A sound"):
            rate, res, secs = nums[:3]
            channels = 2 if "stereo" in q.prompt else 1
            assert answer_bytes == rate * res * secs * channels / 8
        else:
            chars, per = nums[:2]
            assert answer_bytes == chars * per / 8


@pytest.mark.parametrize("seed", SEEDS)
def test_rle(seed: int) -> None:
    for q in logic.rle(seed, 30, "hard"):
        if q.prompt.startswith("Run-length encode"):
            text = q.prompt.split(": ")[1]
            decoded = "".join(ch * int(n) for n, ch in re.findall(r"(\d+)([A-Z])", q.answer))
            assert decoded == text
        else:
            enc = q.prompt.split(": ")[1]
            decoded = "".join(ch * int(n) for n, ch in re.findall(r"(\d+)([A-Z])", enc))
            assert decoded == q.answer


@pytest.mark.parametrize("seed", SEEDS)
def test_huffman(seed: int) -> None:
    def independent(freqs: list[int]) -> int:
        # Build the tree explicitly and sum freq * depth.
        heap = [(f, i, [i]) for i, f in enumerate(freqs)]
        heapq.heapify(heap)
        depth = dict.fromkeys(range(len(freqs)), 0)
        counter = len(freqs)
        while len(heap) > 1:
            fa, _, la = heapq.heappop(heap)
            fb, _, lb = heapq.heappop(heap)
            for leaf in la + lb:
                depth[leaf] += 1
            heapq.heappush(heap, (fa + fb, counter, la + lb))
            counter += 1
        return sum(f * depth[i] for i, f in enumerate(freqs))

    for q in logic.huffman(seed, 20, "hard"):
        freqs = [int(f) for f in re.findall(r"[A-H]: (\d+)", q.prompt)]
        assert int(q.answer.split()[0]) == independent(freqs)


def test_generate_dispatch_and_determinism() -> None:
    a = logic.generate("binary", 5, 6, "easy")
    b = logic.generate("binary", 5, 6, "easy")
    assert a == b and len(a) == 6
    with pytest.raises(ValueError, match="unknown topic"):
        logic.generate("nope", 1, 1, "easy")
