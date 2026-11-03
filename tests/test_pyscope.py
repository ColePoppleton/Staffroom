"""The shared wrong-variable rule (#48): Bugs and Parsons ask ``core.pyscope``
which name a pupil would plausibly type instead of another."""

import ast

from staffroom.core.pyscope import Scopes

FIB = "a = 0\nb = 1\nn = 10\nfor i in range(n):\n    a, b = b, a + b\nprint(n)\n"


def uses(tree: ast.Module, line: int) -> dict[str, ast.Name]:
    return {
        n.id: n
        for n in ast.walk(tree)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.lineno == line
    }


def test_kinds_come_from_the_programs_own_assignments() -> None:
    source = (
        "count = 0\nname = input()\nscores = [1, 2]\nok = count > 1\nbook = {}\n"
        "for s in scores:\n    pass\nfor ch in name:\n    pass\nratio = count / len(scores)\n"
        "x = foo()\nmixed = 1\nmixed = 'one'\n"
    )
    kinds = Scopes(ast.parse(source)).kinds
    assert kinds == {
        "count": "number",
        "name": "str",
        "scores": "list",
        "ok": "bool",
        "book": "dict",
        "s": "number",
        "ch": "str",
        "ratio": "number",
        "x": "unknown",
        "mixed": "unknown",
    }


def test_the_stand_in_is_the_same_kind_most_recently_set_before_the_line() -> None:
    source = "total = 0\nwords = ['a']\ncount = 0\nlater = 1\nprint(total)\n"
    tree = ast.parse(source)
    assert Scopes(tree).stand_in(uses(tree, 5)["total"]) == "later"
    tree = ast.parse("total = 0\nwords = ['a']\ncount = 0\nprint(total)\nlater = 1\n")
    assert Scopes(tree).stand_in(uses(tree, 4)["total"]) == "count"


def test_a_name_set_by_unpacking_is_set_on_that_line() -> None:
    """``a, b = b, a + b`` sets both: the most recent numbers before line 6
    are a and b (a was set first), not the loop counter i."""
    tree = ast.parse(FIB)
    assert Scopes(tree).stand_in(uses(tree, 6)["n"]) == "a"


def test_unknown_kinds_only_on_request() -> None:
    tree = ast.parse("n = 0\na = foo()\nb = bar()\nprint(a)\nprint(n)\n")
    scopes = Scopes(tree)
    a = uses(tree, 4)["a"]
    assert scopes.stand_in(a) is None  # Parsons: never a guess
    assert scopes.stand_in(a, guess_unknown=True) == "b"  # Bugs: another unclear name
    tree = ast.parse("n = 0\nx = foo()\nprint(x)\n")
    x = uses(tree, 3)["x"]
    assert Scopes(tree).stand_in(x, guess_unknown=True) == "n"  # else any name set


def test_functions_and_comprehensions_keep_their_names() -> None:
    source = (
        "rate = 2\n"
        "def pay(hours):\n"
        "    base = 10\n"
        "    return base\n"
        "squares = [k * k for k in range(3)]\n"
        "bonus = 3\n"
        "print(bonus)\n"
    )
    tree = ast.parse(source)
    scopes = Scopes(tree)
    assert scopes.stand_in(uses(tree, 4)["base"]) == "rate"  # the function sees the top level
    # The top level never sees base (the function's) or k (the comprehension's).
    assert scopes.stand_in(uses(tree, 7)["bonus"]) == "rate"
