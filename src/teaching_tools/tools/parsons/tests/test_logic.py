"""Acceptance: the answer key reconstructs to code that parses and is equal
(ignoring blanks and comments) to the input, for a range of programs."""

import ast
import random

import pytest

from teaching_tools.tools.parsons import logic

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
    for line in ("while count < 10:", "if a == b:", "x = x + 1", "return total"):
        result = logic.mutate(line, rng)
        if result:
            kinds.add(result[1])
            assert result[0] != line
    assert {"missing colon", "wrong comparison", "off by one"} & kinds
    assert logic.mutate("return total", rng) is None


def test_too_short_and_invalid() -> None:
    with pytest.raises(ValueError, match="at least two"):
        logic.make_problem("print(1)\n")
    with pytest.raises(SyntaxError):
        logic.make_problem("while True\n    pass\n")
