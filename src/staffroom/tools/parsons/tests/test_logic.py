"""Acceptance: the answer key reconstructs to code that parses and is equal
(ignoring blanks and comments) to the input, for a range of programs."""

import ast
import io
import random
import re
import tokenize

import pytest

from staffroom.core import paths
from staffroom.tools.parsons import logic

PROGRAMS = {
    "while": "count = 0\nwhile count < 10:\n    print(count)\n    count += 1\n",
    "if_elif_else": (
        "mark = int(input('Mark: '))\n"
        "if mark >= 70:\n    print('A')\nelif mark >= 50:\n    print('B')\nelse:\n    print('U')\n"
    ),
    "function": (
        "def total(items):\n    result = 0\n    for item in items:\n        result += item\n"
        "    return result\n\n\nprint(total([1, 2, 3]))\n"
    ),
    "try": "try:\n    n = int(input())\nexcept ValueError:\n    n = 0\nprint(n)\n",
    "nested": (
        "for i in range(3):\n    for j in range(3):\n        if i == j:\n            print(i)\n"
        "        else:\n            print(j)\n"
    ),
    "multiline_stmt": "names = [\n    'a',\n    'b',\n]\nprint(len(names))\n",
    "comments_and_blanks": "# a comment\nx = 1\n\n# another\ny = x + 1\nprint(y)\n",
}


@pytest.mark.parametrize("name", list(PROGRAMS))
@pytest.mark.parametrize("granularity", ["statement", "line"])
def test_key_reconstructs_the_program(name: str, granularity: logic.Granularity) -> None:
    source = PROGRAMS[name]
    if granularity == "line" and name == "multiline_stmt":
        pytest.skip("line granularity cannot keep a multi-line statement together")
    options = logic.Options(seed=3, distractors=2, granularity=granularity)
    problem = logic.make_problem(source, options)
    rebuilt = logic.reconstruct(problem.solution)
    ast.parse(rebuilt)
    assert ast.dump(ast.parse(rebuilt)) == ast.dump(ast.parse(source))
    assert logic.same_program(rebuilt, source)
    # Following the printed answer order gives the same thing.
    by_number = {n: b for n, b in problem.numbered()}
    from_key = logic.reconstruct([by_number[n] for n in problem.answer_order()])
    assert from_key == rebuilt


@pytest.mark.parametrize("seed", range(1, 40))
def test_many_seeds_shuffle_but_never_lose_blocks(seed: int) -> None:
    source = PROGRAMS["function"]
    problem = logic.make_problem(source, logic.Options(seed=seed, distractors=3))
    real = [b for b in problem.shuffled if not b.distractor]
    assert sorted(b.order for b in real) == list(range(len(problem.solution)))
    assert real != problem.solution  # printed order differs from the solution
    assert len(problem.distractor_numbers()) <= 3
    assert all(b.text not in {r.text for r in real} for b in problem.shuffled if b.distractor)
    # Deterministic for a seed.
    again = logic.make_problem(source, logic.Options(seed=seed, distractors=3))
    assert [b.text for b in again.shuffled] == [b.text for b in problem.shuffled]


def test_statement_blocks_keep_headers_and_bodies_apart() -> None:
    blocks = logic.split_statements(PROGRAMS["if_elif_else"])
    assert [b.text for b in blocks] == [
        "mark = int(input('Mark: '))",
        "if mark >= 70:",
        "print('A')",
        "elif mark >= 50:",
        "print('B')",
        "else:",
        "print('U')",
    ]
    assert [b.indent for b in blocks] == [0, 0, 1, 0, 1, 0, 1]


def test_mutations_are_plausible() -> None:
    rng = random.Random(1)
    kinds = set()
    for line in ("while count < 10:", "if a == b:", "x = scores[i + 1]", "return total"):
        result = logic.mutate(line, rng)
        if result:
            kinds.add(result[1])
            assert result[0] != line
    assert {"missing colon", "wrong comparison", "off by one in an index"} & kinds
    assert logic.mutate("return total", rng) is None


def _every_mutation(line: str) -> set[tuple[str, str]]:
    return {r for seed in range(60) if (r := logic.mutate(line, random.Random(seed)))}


@pytest.mark.parametrize(
    "line",
    [
        "scores = [45, 62, 58, 71, 39]",  # data: the pupil cannot know 63 is wrong
        "total = 0",  # a starting value
        "count = count + 1",  # would offer "+ 0" or "+ 2"
        "point = (3, 4)",
        "ages = {'a': 12, 'b': 13}",
        "lookup = {1, 2, 3}",
        "print('Year 9 < Year 10')",  # inside a string
        "x = 5",
    ],
)
def test_data_is_never_changed(line: str) -> None:
    assert _every_mutation(line) == set()


def test_off_by_one_only_on_bounds_a_pupil_can_reason_about() -> None:
    assert {k for _, k in _every_mutation("for i in range(3):")} == {
        "missing colon",
        "off by one in range()",
    }
    assert {m for m, k in _every_mutation("for i in range(1, 10):") if k != "missing colon"} == {
        "for i in range(2, 10):",
        "for i in range(0, 10):",
        "for i in range(1, 9):",
        "for i in range(1, 11):",
    }
    assert {m for m, _ in _every_mutation("print(scores[0])")} == {"print(scores[1])"}
    assert {m for m, _ in _every_mutation("last = items[-1]")} == {"last = items[-2]"}
    assert {m for m, _ in _every_mutation("while i < 10:")} >= {"while i < 9:", "while i < 11:"}
    # A pass mark in an ``if`` is data: the operator may flip, the number may not.
    assert {m for m, _ in _every_mutation("if average >= 50:")} == {
        "if average >= 50",
        "if average > 50:",
    }
    assert {m for m, _ in _every_mutation("elif mark >= 70:")} == {
        "elif mark >= 70",
        "elif mark > 70:",
    }


@pytest.mark.parametrize(
    "line", ["x = items[i - 1]", "x = items[i + 1]", "while i < len(items) - 1:", "y = a[2 * i]"]
)
def test_off_by_one_never_makes_a_do_nothing_operation(line: str) -> None:
    made = {m for m, k in _every_mutation(line) if k.startswith("off by one")}
    assert made, line
    for mutated in made:
        assert not re.search(r"[-+] 0\b|\* 1\b|\[-0\]", mutated), mutated


# ----------------------------------------------------- the corpus (#19)
CORPUS = {
    **PROGRAMS,
    "year9": (paths.examples_dir() / "year9.py").read_text(),
    "year9_tabs": (paths.examples_dir() / "year9.py").read_text().replace("    ", "\t"),
    "plugin": "count = 0\nwhile count < 10:\n    print(count)\n    count += 1\n",
}


def _distractors(name: str) -> list[logic.Block]:
    made: list[logic.Block] = []
    for granularity in ("statement", "line"):
        if granularity == "line" and name == "multiline_stmt":
            continue
        for seed in range(1, 21):
            for count in (2, 10):
                options = logic.Options(seed=seed, distractors=count, granularity=granularity)
                problem = logic.make_problem(CORPUS[name], options)
                made += [b for b in problem.shuffled if b.distractor]
    return made


def _tokens(line: str) -> list[tokenize.TokenInfo]:
    found = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(line).readline):
            if tok.type not in (tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER):
                found.append(tok)
    except tokenize.TokenError:
        pass
    return found


def _explain(distractor: str, real_lines: list[str]) -> str:
    """Say independently of ``logic`` what is wrong with ``distractor``,
    or fail: the one token that differs from a real line, and where it sits."""
    if distractor + ":" in real_lines:
        return "missing colon"
    mine = _tokens(distractor)
    for real in real_lines:
        theirs = _tokens(real)
        if len(theirs) != len(mine):
            continue
        diff = [
            i for i, (a, b) in enumerate(zip(mine, theirs, strict=True)) if a.string != b.string
        ]
        if len(diff) != 1:
            continue
        i = diff[0]
        a, b = mine[i].string, theirs[i].string
        ops = {"<", "<=", ">", ">=", "==", "!="}
        if a in ops and b in ops:
            return "wrong comparison"
        assert mine[i].type == tokenize.NUMBER and abs(int(a) - int(b)) == 1, (distractor, real)
        before = [t.string for t in mine[:i]]
        assert before[-1:] not in (["+"], ["-"]) or a != "0", distractor  # no "+ 0"
        opener = max((j for j, t in enumerate(before) if t == "["), default=-1)
        closed = opener >= 0 and "]" in before[opener:]
        if "range" in before and "(" in before[before.index("range") :]:
            return "off by one in range()"
        if opener > 0 and not closed and mine[opener - 1].type == tokenize.NAME:
            return "off by one in an index"
        assert before[0] == "while", f"off by one outside a bound: {distractor!r}"
        return "off by one in a loop condition"
    raise AssertionError(f"no real line explains {distractor!r}")


@pytest.mark.parametrize("name", list(CORPUS))
def test_every_distractor_in_the_corpus_is_wrong_in_a_way_the_sheet_shows(name: str) -> None:
    real_lines = [b.lines[0] for b in logic.split(CORPUS[name], "line")]
    real_lines += [b.lines[0] for b in logic.split(CORPUS[name], "statement")]
    for block in _distractors(name):
        assert block.kind in logic.KINDS
        assert _explain(block.lines[0], real_lines) == block.kind, block


def test_the_corpus_uses_these_kinds_and_no_others() -> None:
    kinds = {name: sorted({b.kind for b in _distractors(name)}) for name in CORPUS}
    assert kinds == {
        "while": ["missing colon", "off by one in a loop condition", "wrong comparison"],
        "if_elif_else": ["missing colon", "wrong comparison"],
        "function": ["missing colon"],
        "try": ["missing colon"],
        "nested": ["missing colon", "off by one in range()", "wrong comparison"],
        "multiline_stmt": [],
        "comments_and_blanks": [],
        "year9": ["missing colon", "wrong comparison"],
        "year9_tabs": ["missing colon", "wrong comparison"],
        "plugin": ["missing colon", "off by one in a loop condition", "wrong comparison"],
    }


def test_the_default_year9_sheet_changes_no_data() -> None:
    problem = logic.make_problem(CORPUS["year9"], logic.Options())
    made = [b.lines[0] for b in problem.shuffled if b.distractor]
    assert len(made) == 2
    assert not [m for m in made if m.startswith(("scores =", "total =", "count ="))]


def test_a_program_whose_distractors_did_not_change_keeps_its_sheet() -> None:
    """``nested`` only had off-by-ones in ``range()``: its sheets are as before #19."""
    statement = logic.make_problem(PROGRAMS["nested"], logic.Options(seed=3, distractors=2))
    assert [(b.text, b.distractor) for b in statement.shuffled] == [
        ("for i in range(3):", False),
        ("for i in range(3)", True),
        ("if i == j:", False),
        ("print(i)", False),
        ("print(j)", False),
        ("for j in range(3):", False),
        ("if i != j:", True),
        ("else:", False),
    ]
    options = logic.Options(seed=7, distractors=3, granularity="line")
    line = logic.make_problem(PROGRAMS["nested"], options)
    assert [(b.text, b.distractor) for b in line.shuffled] == [
        ("if i == j:", False),
        ("print(j)", False),
        ("else:", False),
        ("for i in range(2):", True),
        ("for j in range(3)", True),
        ("else", True),
        ("print(i)", False),
        ("for j in range(3):", False),
        ("for i in range(3):", False),
    ]


def test_too_short_and_invalid() -> None:
    with pytest.raises(ValueError, match="at least two"):
        logic.make_problem("print(1)\n")
    with pytest.raises(SyntaxError):
        logic.make_problem("while True\n    pass\n")
