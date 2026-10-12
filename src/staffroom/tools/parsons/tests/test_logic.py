"""Acceptance: the answer key reconstructs to code that parses and is equal
(ignoring blanks and comments) to the input, for a range of programs."""

import ast
import io
import keyword
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


def _assigned(source: str) -> set[str]:
    """Every name the program sets (a variable a pupil can see on the sheet)."""
    tree = ast.parse(source.replace("\t", "    "))
    return {
        n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    }


def _parses(line: str) -> bool:
    try:
        ast.parse(line + "\n    pass" if line.endswith(":") else line)
    except SyntaxError:
        return False
    return True


def _explain(distractor: str, real_lines: list[str], assigned: set[str]) -> str:
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
        if mine[i].type == tokenize.NAME and theirs[i].type == tokenize.NAME:
            # Another of the program's own variables, read where the real one
            # was: not an attribute, not a function called, and still Python.
            assert a in assigned and b in assigned, (distractor, real)
            assert not keyword.iskeyword(a) and not keyword.iskeyword(b), distractor
            assert i == 0 or mine[i - 1].string != ".", distractor
            assert i + 1 == len(mine) or mine[i + 1].string != "(", distractor
            assert _parses(distractor), distractor
            return "wrong variable"
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
    assigned = _assigned(CORPUS[name])
    for block in _distractors(name):
        assert block.kind in logic.KINDS
        assert _explain(block.lines[0], real_lines, assigned) == block.kind, block
        assert block.original in real_lines, block  # the key's "Looks like"


def test_the_corpus_uses_these_kinds_and_no_others() -> None:
    kinds = {name: sorted({b.kind for b in _distractors(name)}) for name in CORPUS}
    assert kinds == {
        "while": ["missing colon", "off by one in a loop condition", "wrong comparison"],
        "if_elif_else": ["missing colon", "wrong comparison"],
        "function": ["missing colon"],
        "try": ["missing colon"],
        "nested": [
            "missing colon",
            "off by one in range()",
            "wrong comparison",
            "wrong variable",
        ],
        "multiline_stmt": [],
        "comments_and_blanks": ["wrong variable"],
        "year9": ["missing colon", "wrong comparison", "wrong variable"],
        "year9_tabs": ["missing colon", "wrong comparison", "wrong variable"],
        "plugin": ["missing colon", "off by one in a loop condition", "wrong comparison"],
    }


def test_the_default_year9_sheet_changes_no_data() -> None:
    problem = logic.make_problem(CORPUS["year9"], logic.Options())
    made = [b for b in problem.shuffled if b.distractor]
    assert len(made) == 2
    for block in made:
        # Only names or punctuation differ: every number and string is as written.
        literals = [
            t.string
            for t in _tokens(block.lines[0])
            if t.type in (tokenize.NUMBER, tokenize.STRING)
        ]
        original = [
            t.string
            for t in _tokens(block.original)
            if t.type in (tokenize.NUMBER, tokenize.STRING)
        ]
        assert literals == original, block


def test_year9_at_seed_1_has_wrong_variables() -> None:
    """A straight-line program gets as many distractors as asked, not just colons (#29)."""
    for granularity in ("statement", "line"):
        options = logic.Options(seed=1, distractors=4, granularity=granularity)
        problem = logic.make_problem(CORPUS["year9"], options)
        assert [(b.lines[0], b.kind) for b in problem.shuffled if b.distractor] == [
            ("if average >= 50", "missing colon"),
            ('print("Average:", count)', "wrong variable"),
            ("count = total + 1", "wrong variable"),
            ("average = count / count", "wrong variable"),
        ]


def test_wrong_variables_in_year9() -> None:
    """Each name read is swapped for the number most recently set before its
    line; the list, the loop's own header and the literals are left alone."""
    swaps = logic.variable_swaps(logic.normalise(CORPUS["year9"]))
    assert {line: [(s.old, s.new) for s in found] for line, found in swaps.items()} == {
        6: [("total", "score"), ("score", "count")],  # total = total + score
        7: [("count", "total")],  # count = count + 1
        8: [("total", "count"), ("count", "total")],  # average = total / count
        9: [("average", "count")],  # if average >= 50:
        13: [("average", "count")],  # print("Average:", average)
    }


@pytest.mark.parametrize(
    "source",
    [
        # Not set yet when the line runs: no stand-in.
        "total = 0\nprint(total)\ncount = 0\n",
        # A different kind: never the list for a number, or a string for a number.
        "scores = [1, 2]\nname = 'Sam'\ntotal = 0\nprint(total)\n",
        # Data and calls are left alone: names in a list, an f-string, a call's function.
        "a = 1\nb = 2\npair = [a, b]\nprint(f'{a}')\n",
        # A parameter's kind is unknown, so it is never swapped or swapped in.
        "def area(w, h):\n    return w * h\n",
        # The loop variable of a comprehension lives only inside it.
        "n = 3\nsquares = [i * i for i in range(n)]\n",
    ],
)
def test_no_wrong_variable_without_a_plausible_stand_in(source: str) -> None:
    assert logic.variable_swaps(source) == {}


def test_wrong_variables_stay_in_their_function() -> None:
    source = (
        "rate = 2\n"
        "def pay(hours):\n"
        "    base = 10\n"
        "    extra = 5\n"
        "    return base + extra\n"
        "bonus = 3\n"
        "print(rate + bonus)\n"
    )
    swaps = logic.variable_swaps(source)
    # Inside the function: its own numbers, and rate from the top level; never
    # bonus, set after it. At the top level, never the function's locals.
    assert [(s.old, s.new) for s in swaps[5]] == [("base", "extra"), ("extra", "base")]
    assert [(s.old, s.new) for s in swaps[7]] == [("rate", "bonus"), ("bonus", "rate")]


def test_wrong_variables_are_seed_reproducible() -> None:
    for seed in (1, 2, 3):
        options = logic.Options(seed=seed, distractors=4)
        first = logic.make_problem(CORPUS["year9"], options)
        again = logic.make_problem(CORPUS["year9"], options)
        assert [b.text for b in first.shuffled] == [b.text for b in again.shuffled]


def test_a_program_whose_distractors_did_not_change_keeps_its_sheet() -> None:
    """``while`` and ``if_elif_else`` have one variable each, so no wrong
    variable: their sheets are as before #29 (and #19)."""
    statement = logic.make_problem(PROGRAMS["while"], logic.Options(seed=3, distractors=2))
    assert [(b.text, b.distractor) for b in statement.shuffled] == [
        ("count = 0", False),
        ("while count < 9:", True),
        ("print(count)", False),
        ("count += 1", False),
        ("while count < 11:", True),
        ("while count < 10:", False),
    ]
    options = logic.Options(seed=7, distractors=3, granularity="line")
    line = logic.make_problem(PROGRAMS["if_elif_else"], options)
    assert [(b.text, b.distractor) for b in line.shuffled] == [
        ("elif mark >= 50", True),
        ("print('A')", False),
        ("else:", False),
        ("elif mark >= 50:", False),
        ("print('B')", False),
        ("mark = int(input('Mark: '))", False),
        ("else", True),
        ("if mark >= 70:", False),
        ("if mark >= 70", True),
        ("print('U')", False),
    ]


def test_too_short_and_invalid() -> None:
    with pytest.raises(ValueError, match="at least two"):
        logic.make_problem("print(1)\n")
    with pytest.raises(SyntaxError):
        logic.make_problem("while True\n    pass\n")
