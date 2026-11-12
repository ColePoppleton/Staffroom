"""Lesson sheets (#75): one skill each, a worked example, a climb, answers checked.

Every answer is checked here by independent computation (``int(x, 2)``, a parser over
the printed expression, a Huffman tree built another way), never by the generator's
own arithmetic.
"""

from __future__ import annotations

import heapq
import itertools
import re
from collections.abc import Callable
from fractions import Fraction

import pytest

from staffroom.core import spec
from staffroom.tools.worksheet import lessons, logic
from staffroom.tools.worksheet.lessons import LESSONS, SECTIONS, Lesson, Settings, make_lesson
from staffroom.tools.worksheet.panel import lesson_choice
from staffroom.tools.worksheet.tests.test_generators import evaluate_gates

DIFFS = ("easy", "medium", "hard")
SEEDS = (1, 7, 42, 1234)
TAUGHT = [lesson for lesson in LESSONS.values() if not lesson.review]


def bits(s: str) -> int:
    return int(s.replace(" ", ""), 2)


def signed(n: int) -> int:
    return n - 256 if n >= 128 else n


# ---------------------------------------------------------------- checkers, one per kind
# Each takes (prompt, answer) and returns True when the answer is right. A prompt that
# is not of its kind fails its pattern, so the checker also proves the question's kind.
def _d2b(p: str, a: str) -> bool:
    m = re.fullmatch(r"Convert (\d+) to binary \(8 bits\)\.", p)
    return bool(m) and len(a.replace(" ", "")) == 8 and bits(a) == int(m.group(1))  # type: ignore[union-attr]


def _b2d(p: str, a: str) -> bool:
    m = re.fullmatch(r"Convert ([01]{4} [01]{4}) to denary\.", p)
    return bool(m) and int(a) == bits(m.group(1))  # type: ignore[union-attr]


def _b2h(p: str, a: str) -> bool:
    m = re.fullmatch(r"Convert ([01]{4}(?: [01]{4})?) \(binary\) to hexadecimal\.", p)
    return bool(m) and int(a, 16) == bits(m.group(1)) and len(a) == len(m.group(1)) // 4  # type: ignore[union-attr]


def _h2b(p: str, a: str) -> bool:
    m = re.fullmatch(r"Convert ([0-9A-F]{1,2}) \(hex\) to binary \((\d) bits\)\.", p)
    if not m:
        return False
    return len(a.replace(" ", "")) == int(m.group(2)) and bits(a) == int(m.group(1), 16)


def _d2h(p: str, a: str) -> bool:
    m = re.fullmatch(r"Convert (\d+) to hexadecimal\.", p)
    return bool(m) and int(a, 16) == int(m.group(1))  # type: ignore[union-attr]


def _h2d(p: str, a: str) -> bool:
    m = re.fullmatch(r"Convert ([0-9A-F]{1,2}) \(hex\) to denary\.", p)
    return bool(m) and int(a) == int(m.group(1), 16)  # type: ignore[union-attr]


def _add(p: str, a: str) -> bool:
    m = re.fullmatch(r"Add ([01]{4} [01]{4}) and ([01]{4} [01]{4})\.", p)
    if not m:
        return False
    total = bits(m.group(1)) + bits(m.group(2))
    # AQA 8525 3.3.4: answers never carry beyond the 8th bit.
    return total <= 255 and bits(a) == total


def _overflow(p: str, a: str) -> bool:
    m = re.match(r"Add ([01]{4} [01]{4}) and ([01]{4} [01]{4}) \(8-bit\)\.", p)
    if not m:
        return False
    total = bits(m.group(1)) + bits(m.group(2))
    head, *rest = a.split("; ")
    result, flag = head.split(", overflow: ")
    ok = bits(result) == total % 256 and (flag == "yes") == (total > 255)
    if rest:
        ok = ok and rest == [f"stores {total % 256}, should be {total}"]
    return ok


def _lshift(p: str, a: str) -> bool:
    m = re.fullmatch(
        r"Apply a logical shift (left|right) by (\d) to ([01]{4} [01]{4})\. "
        r"Give the result and its effect on the value\.",
        p,
    )
    if not m:
        return False
    direction, places, pattern = m.group(1), int(m.group(2)), m.group(3).replace(" ", "")
    shifted = (
        pattern[places:] + "0" * places if direction == "left" else "0" * places + pattern[:-places]
    )
    result, effect = a.split("; ")
    word = "multiplies" if direction == "left" else "divides"
    return result.replace(" ", "") == shifted and effect.startswith(f"{word} by {2**places}")


def _ashift(p: str, a: str) -> bool:
    m = re.match(r"Apply an arithmetic shift right by (\d) to ([01]{4} [01]{4}) ", p)
    if not m:
        return False
    places, pattern = int(m.group(1)), m.group(2).replace(" ", "")
    shifted = pattern[0] * places + pattern[:-places]  # the sign bit fills the gaps
    result, values = a.split("; ")
    return result.replace(" ", "") == shifted and values == (
        f"{signed(int(pattern, 2))} -> {signed(int(shifted, 2))}"
    )


def _to_tc(p: str, a: str) -> bool:
    m = re.fullmatch(r"Write -(\d+) as an 8-bit two's complement number\.", p)
    return bool(m) and bits(a) == 256 - int(m.group(1))  # type: ignore[union-attr]


def _from_tc(p: str, a: str) -> bool:
    m = re.fullmatch(r"What denary value is ([01]{4} [01]{4}) \(two's complement\)\?", p)
    return bool(m) and int(a) == signed(bits(m.group(1)))  # type: ignore[union-attr]


def _table(gates: int, inputs: int) -> Callable[[str, str], bool]:
    def check(p: str, a: str) -> bool:
        m = re.fullmatch(r"Complete the truth table for Q = (.+)\.", p)
        if not m:
            return False
        expr = m.group(1)
        names = sorted(set(re.findall(r"\b[ABC]\b", expr)))
        if len(names) != inputs:
            return False
        if len(re.findall(r"\b(?:AND|OR|XOR|NAND|NOR)\b", expr)) != gates:
            return False
        rows = itertools.product([False, True], repeat=inputs)
        want = [int(evaluate_gates(expr, dict(zip(names, r, strict=True)))) for r in rows]
        got = [int(x) for x in a.removeprefix("Q = ").split()[: 2**inputs]]
        return got == want

    return check


def _simplify(p: str, a: str) -> bool:
    m = re.fullmatch(r"Simplify: (.+)", p)
    if not m:
        return False
    rows = itertools.product([False, True], repeat=3)
    return all(
        evaluate_gates(m.group(1), dict(zip("ABC", r, strict=True)))
        == evaluate_gates(a, dict(zip("ABC", r, strict=True)))
        for r in rows
    )


UNIT_BYTES = {"bytes": 1, "KB": 1000, "MB": 1000**2, "KiB": 1024, "MiB": 1024**2}


def _size(pattern: str) -> Callable[[str, str], bool]:
    def check(p: str, a: str) -> bool:
        m = re.match(pattern, p)
        if not m:
            return False
        product = 1
        for g in m.groups():
            product *= int(g.replace(",", ""))
        value, unit = a.split(" ")
        exact = Fraction(product, 8 * UNIT_BYTES[unit])
        asked = re.search(r"in (bytes|KB|MB|KiB|MiB)", p)
        if asked is None or asked.group(1) != unit:
            return False
        return abs(Fraction(value.replace(",", "")) - exact) <= Fraction(1, 200)

    return check


def _rle_enc(p: str, a: str) -> bool:
    m = re.fullmatch(r"Run-length encode: ([A-Z]+)", p)
    if not m:
        return False
    runs = [f"{len(list(g))}{ch}" for ch, g in itertools.groupby(m.group(1))]
    return a == " ".join(runs)


def _rle_dec(p: str, a: str) -> bool:
    m = re.fullmatch(r"Decode the run-length encoding: ((?:\d+[A-Z] ?)+)", p)
    if not m:
        return False
    return a == "".join(ch * int(n) for n, ch in re.findall(r"(\d+)([A-Z])", m.group(1)))


def huffman_bits(freqs: dict[str, int]) -> int:
    """Build the tree, then sum frequency * depth (not the sum of merges)."""
    heap: list[tuple[int, int, list[str]]] = [
        (f, i, [ch]) for i, (ch, f) in enumerate(freqs.items())
    ]
    heapq.heapify(heap)
    depth = dict.fromkeys(freqs, 0)
    tie = len(heap)
    while len(heap) > 1:
        w1, _, s1 = heapq.heappop(heap)
        w2, _, s2 = heapq.heappop(heap)
        for ch in s1 + s2:
            depth[ch] += 1
        heapq.heappush(heap, (w1 + w2, tie, s1 + s2))
        tie += 1
    return sum(freqs[ch] * depth[ch] for ch in freqs)


def _huffman(p: str, a: str) -> bool:
    m = re.match(r"Build a Huffman tree for the frequencies ((?:[A-H]: \d+(?:, )?)+)\.", p)
    if not m:
        return False
    freqs = {ch: int(f) for ch, f in re.findall(r"([A-H]): (\d+)", m.group(1))}
    total = huffman_bits(freqs)
    parts = a.split("; ")
    if parts[0] != f"{total} bits":
        return False
    if len(parts) > 1:
        chars = sum(freqs.values())
        return (
            parts[1]
            == f"ASCII needs {chars} × 8 = {chars * 8} bits, a saving of {chars * 8 - total}"
        )
    return True


CHECK: dict[str, Callable[[str, str], bool]] = {
    "d2b": _d2b,
    "b2d": _b2d,
    "b2h": _b2h,
    "h2b": _h2b,
    "d2h": _d2h,
    "h2d": _h2d,
    "add": _add,
    "overflow": _overflow,
    "lshift": _lshift,
    "ashift": _ashift,
    "to_tc": _to_tc,
    "from_tc": _from_tc,
    "one-gate": _table(1, 2),
    "two-gates": _table(2, 3),
    "three-gates": _table(3, 3),
    "simplify": _simplify,
    "image": _size(r"An image is (\d+) × (\d+) pixels with a colour depth of (\d+) bit"),
    "sound": _size(
        r"A sound is sampled at ([\d,]+) Hz with a sample resolution of (\d+) bits for (\d+) second"
    ),
    "text": _size(r"A text file holds ([\d,]+) characters in .*?\((\d+) bits per character\)"),
    "rle_enc": _rle_enc,
    "rle_dec": _rle_dec,
    "huffman": _huffman,
}


def _sheets(lesson: Lesson) -> list[lessons.LessonSheet]:
    out = []
    for difficulty, seed, board in itertools.product(DIFFS, SEEDS, spec.BOARDS):
        settings = Settings(board=board)
        out.append(make_lesson(lesson, seed, 10, difficulty, settings))  # type: ignore[arg-type]
    return out


# ---------------------------------------------------------------- one skill per lesson
@pytest.mark.parametrize("lesson", TAUGHT, ids=lambda les: les.key)
def test_every_question_is_the_lessons_own_skill_and_right(lesson: Lesson) -> None:
    assert lesson.kinds and set(lesson.kinds) <= set(CHECK)
    for sheet in _sheets(lesson):
        for q in sheet.questions:
            assert q.kind in lesson.kinds, (lesson.key, q.kind)
            assert CHECK[q.kind](q.prompt, q.answer), (lesson.key, q.prompt, q.answer)
            # and no other lesson's checker accepts it: the prompt is of one kind only
            others = [k for k in CHECK if k not in lesson.kinds and CHECK[k](q.prompt, q.answer)]
            assert not others, (q.prompt, others)


@pytest.mark.parametrize("lesson", TAUGHT, ids=lambda les: les.key)
def test_the_worked_example_is_solved_and_right(lesson: Lesson) -> None:
    for sheet in _sheets(lesson):
        ex = sheet.example
        assert ex.steps and all(isinstance(s, str) for s in ex.steps) and ex.answer
        assert any(CHECK[k](ex.question, ex.answer) for k in lesson.kinds), ex
        assert ex.question not in [q.prompt for q in sheet.questions]  # not set again


# ---------------------------------------------------------------- the shape of a sheet
@pytest.mark.parametrize("lesson", TAUGHT, ids=lambda les: les.key)
def test_a_sheet_climbs_from_warm_up_to_stretch(lesson: Lesson) -> None:
    assert lesson.aim.endswith(".") and lesson.ranges is not None
    for difficulty in DIFFS:
        ranges = lesson.ranges(difficulty)  # type: ignore[arg-type]
        lows, highs = [lo for lo, _ in ranges], [hi for _, hi in ranges]
        assert lows == sorted(lows) and highs == sorted(highs), (difficulty, ranges)
        assert highs[2] > highs[0] or lows[2] > lows[0], (difficulty, ranges)
    for difficulty, seed in itertools.product(DIFFS, SEEDS):
        sheet = make_lesson(lesson, seed, 10, difficulty, Settings())  # type: ignore[arg-type]
        assert [p.name for p in sheet.parts] == list(SECTIONS)
        assert [len(p.questions) for p in sheet.parts] == [3, 5, 2]
        ranges = lesson.ranges(difficulty)  # type: ignore[arg-type]
        for part, (lo, hi) in zip(sheet.parts, ranges, strict=True):
            assert part.hint
            for q in part.questions:
                assert lo <= q.size <= hi, (part.name, q.prompt, q.size, (lo, hi))


def test_difficulty_moves_the_whole_climb_up() -> None:
    for lesson in TAUGHT:
        assert lesson.ranges is not None
        easy, hard = lesson.ranges("easy"), lesson.ranges("hard")
        assert all(e[1] <= h[1] for e, h in zip(easy, hard, strict=True)), lesson.key


@pytest.mark.parametrize("count", [1, 2, 3, 4, 10, 25, 60])
def test_the_count_is_shared_out_and_every_question_is_numbered(count: int) -> None:
    sheet = make_lesson(LESSONS["binary/denary-to-binary"], 1, count, "medium", Settings())
    assert len(sheet.questions) == count
    if count >= 3:
        assert all(p.questions for p in sheet.parts) and len(sheet.parts) == 3


def test_a_lesson_sheet_is_the_same_for_the_same_seed() -> None:
    for lesson in TAUGHT:
        one = make_lesson(lesson, 5, 10, "medium", Settings(board="aqa"))
        assert one == make_lesson(lesson, 5, 10, "medium", Settings(board="aqa")), lesson.key


def test_truth_table_lessons_use_only_the_boards_gates() -> None:
    for key in ("logic/one-gate", "logic/two-gates", "logic/three-gates"):
        for board in spec.BOARDS:
            for difficulty in DIFFS:
                sheet = make_lesson(LESSONS[key], 3, 20, difficulty, Settings(board=board))  # type: ignore[arg-type]
                used = {w for q in sheet.questions for w in re.findall(r"\b[A-Z]{2,4}\b", q.prompt)}
                assert used - {"NOT"} <= set(logic.gate_set(board)), (key, board, used)


def test_file_sizes_follow_the_boards_units() -> None:
    """Edexcel 2.3.1 measures in kibibytes; OCR 1.2.3 and AQA 3.3.3 in thousands."""
    for board, unit in (("ocr", "KB"), ("aqa", "KB"), ("edexcel", "KiB")):
        sheet = make_lesson(LESSONS["file-sizes/image"], 1, 10, "medium", Settings(board=board))
        practice = sheet.parts[1].questions
        assert all(q.answer.endswith(f" {unit}") for q in practice), (board, practice[0].answer)


def test_the_key_gives_working_for_every_question() -> None:
    for lesson in TAUGHT:
        sheet = make_lesson(lesson, 2, 10, "hard", Settings(board="aqa"))
        for q in sheet.questions:
            assert q.working.strip(), (lesson.key, q.prompt)


# ---------------------------------------------------------------- spec points per board
# The verified map (#75). Checked against core/spec/{ocr,aqa,edexcel}.toml and the
# published specifications named in lessons.SPEC_SOURCES. A change here is a change
# to what the tool tells a teacher is on their exam: make it on purpose.
VERIFIED: dict[str, dict[str, str]] = {
    "binary/denary-to-binary": {"ocr": "1.2.4", "aqa": "3.3.2", "edexcel": "2.1.3"},
    "binary/binary-to-denary": {"ocr": "1.2.4", "aqa": "3.3.2", "edexcel": "2.1.3"},
    "binary/binary-and-hex": {"ocr": "1.2.4", "aqa": "3.3.2", "edexcel": "2.1.6"},
    "binary/denary-and-hex": {"ocr": "1.2.4", "aqa": "3.3.2"},
    "arithmetic/addition": {"ocr": "1.2.4", "aqa": "3.3.4", "edexcel": "2.1.4"},
    "arithmetic/overflow": {"ocr": "1.2.4", "edexcel": "2.1.5"},
    "arithmetic/logical-shifts": {"ocr": "1.2.4", "aqa": "3.3.4", "edexcel": "2.1.4"},
    "arithmetic/arithmetic-shifts": {"edexcel": "2.1.4"},
    "twos-complement/to-twos-complement": {"edexcel": "2.1.3"},
    "twos-complement/from-twos-complement": {"edexcel": "2.1.3"},
    "logic/one-gate": {"ocr": "2.4.1", "aqa": "3.4.2", "edexcel": "1.3.1"},
    "logic/two-gates": {"ocr": "2.4.1", "aqa": "3.4.2", "edexcel": "1.3.1"},
    "logic/three-gates": {"ocr": "2.4.1", "aqa": "3.4.2", "edexcel": "1.3.1"},
    "logic/simplification": {},
    "file-sizes/image": {"ocr": "1.2.3", "aqa": "3.3.6", "edexcel": "2.3.1"},
    "file-sizes/sound": {"ocr": "1.2.3", "aqa": "3.3.7", "edexcel": "2.3.1"},
    "file-sizes/text": {"ocr": "1.2.3", "aqa": "3.3.8", "edexcel": "2.3.1"},
    "compression/rle-encode": {"aqa": "3.3.8"},
    "compression/rle-decode": {"aqa": "3.3.8"},
    "compression/huffman": {"aqa": "3.3.8"},
}


def test_every_lesson_has_its_verified_spec_points() -> None:
    assert {les.key: dict(les.spec) for les in TAUGHT} == VERIFIED


@pytest.mark.parametrize("board", list(spec.BOARDS))
def test_every_spec_point_is_in_the_boards_toml(board: str) -> None:
    codes = {p.code: p.title for p in spec.load_taxonomy(board)}
    for lesson in TAUGHT:
        if board in lesson.spec:
            assert lesson.spec[board] in codes, (lesson.key, board, lesson.spec[board])


def test_every_unit_has_lessons_on_some_board_or_says_why() -> None:
    for unit in lessons.UNITS:
        taught = [les for les in unit.lessons if not les.review]
        assert taught, unit.slug
        for board in spec.BOARDS:
            reasons = [lessons.off_board_reason(les, board, spec.SHORT_NAMES) for les in taught]
            for les, reason in zip(taught, reasons, strict=True):
                assert bool(reason) == (board not in les.spec), (les.key, board, reason)


def test_off_board_lessons_are_greyed_in_the_panel_with_a_reason() -> None:
    choice = lesson_choice("ocr")
    items = {i.value: i for g in choice.groups for i in g.items}
    tc = items["twos-complement/to-twos-complement"]
    assert tc.dim and tc.note == "On Edexcel only"
    assert items["logic/simplification"].note == "A level: not on any GCSE"
    assert (
        items["binary/denary-to-binary"].tag == "OCR 1.2.4"
        and not items["binary/denary-to-binary"].dim
    )
    assert not items["binary/review"].dim and items["binary/review"].divided
    assert items["twos-complement/review"].dim  # a unit OCR lacks greys its Review too
    assert items["logic/review-simplification"].dim  # A level, like the lesson
    assert not items["logic/review-truth-tables"].dim
    groups = {g.value: g for g in choice.groups}
    assert groups["twos-complement"].dim and groups["compression"].dim
    assert not groups["binary"].dim
    edexcel = {i.value: i for g in lesson_choice("edexcel").groups for i in g.items}
    assert not edexcel["twos-complement/to-twos-complement"].dim
    assert edexcel["binary/denary-and-hex"].dim and edexcel["binary/denary-and-hex"].note == (
        "On OCR and AQA only"
    )
    assert "Pearson Edexcel 1CP2" in lesson_choice("edexcel").note


# ---------------------------------------------------------------- names
def test_every_review_covers_lessons_of_its_own_unit() -> None:
    for les in LESSONS.values():
        if les.review:
            assert les.covers, les.key
            assert all(f"{les.unit}/{slug}" in LESSONS for slug in les.covers), les.key


def test_resolve_takes_units_lessons_and_old_topics() -> None:
    assert lessons.resolve("binary").key == "binary/review"
    assert lessons.resolve("binary", "denary-to-binary").key == "binary/denary-to-binary"
    assert lessons.resolve("binary/binary-and-hex").key == "binary/binary-and-hex"
    assert lessons.resolve("shifts").key == "arithmetic/review-shifts"
    assert lessons.resolve("binary_addition").key == "arithmetic/review-addition"
    assert lessons.resolve("file_size").key == "file-sizes/review"
    assert lessons.resolve("twos_complement").key == "twos-complement/review"
    assert lessons.resolve("compression").key == "compression/review-rle"
    for bad in (("nope", None), ("binary", "nope")):
        with pytest.raises(ValueError, match="choose from"):
            lessons.resolve(*bad)
