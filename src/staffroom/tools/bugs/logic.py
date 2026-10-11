"""Pure logic for bugs: find places a controlled error can be injected and
apply exactly one per variant. No I/O."""

from __future__ import annotations

import ast
import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

TIMEOUT = 4.0  # seconds each variant may run; the panel description quotes it

Kind = Literal[
    "comparison_flip",
    "off_by_one",
    "missing_colon",
    "missing_bracket",
    "wrong_variable",
    "indentation_slip",
    "string_int",
]
KIND_LABELS: dict[Kind, str] = {
    "comparison_flip": "comparison flipped",
    "off_by_one": "off by one",
    "missing_colon": "missing colon",
    "missing_bracket": "missing bracket",
    "wrong_variable": "wrong variable name",
    "indentation_slip": "indentation slip",
    "string_int": "string / integer confusion",
}
_FLIP = {"<": "<=", "<=": "<", ">": ">=", ">=": ">", "==": "!=", "!=": "=="}
_OP_TEXT = {
    ast.Lt: "<",
    ast.LtE: "<=",
    ast.Gt: ">",
    ast.GtE: ">=",
    ast.Eq: "==",
    ast.NotEq: "!=",
}


@dataclass
class Options:
    count: int = field(default=4, metadata={"label": "Variants", "min": 1, "max": 20})
    seed: int = field(default=1, metadata={"label": "Seed", "min": 0, "max": 999_999})
    silent: int = field(
        default=0,
        metadata={
            "label": "Silent bugs allowed",
            "min": 0,
            "max": 20,
            "help": "Bugs that leave the output unchanged. At 0 they are swapped for bugs "
            "pupils can see by running the code; raise it for a read-the-code discussion.",
        },
    )
    comparison_flip: bool = field(default=True, metadata={"label": "Comparison flipped"})
    off_by_one: bool = field(default=True, metadata={"label": "Off by one"})
    missing_colon: bool = field(default=True, metadata={"label": "Missing colon"})
    missing_bracket: bool = field(default=True, metadata={"label": "Missing bracket"})
    wrong_variable: bool = field(default=True, metadata={"label": "Wrong variable name"})
    indentation_slip: bool = field(default=True, metadata={"label": "Indentation slip"})
    string_int: bool = field(default=True, metadata={"label": "String / integer confusion"})
    formats: Literal["both", "docx", "pdf"] = field(default="both", metadata={"label": "Output"})

    def kinds(self) -> list[Kind]:
        return [k for k in KIND_LABELS if getattr(self, k)]


@dataclass(frozen=True)
class Mutation:
    kind: Kind
    line: int  # 1-based
    original: str
    mutated: str
    note: str

    @property
    def label(self) -> str:
        return KIND_LABELS[self.kind]


@dataclass
class Variant:
    number: int
    mutation: Mutation
    source: str
    outcome: str = ""  # filled by the plugin after a sandbox run
    silent: bool = False  # runs exactly like the original; the sheet says so


# ---------------------------------------------------------------- candidates
def candidates(source: str) -> list[Mutation]:
    """Every single-line mutation the program admits, across all kinds."""
    tree = ast.parse(source)
    lines = source.splitlines()
    found: list[Mutation] = []
    names = _assigned_names(tree)
    scope = _Scopes(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and _one_line(node):
            op = _OP_TEXT.get(type(node.ops[0]))
            if op:
                seg = _segment(lines, node)
                left_end = node.left.end_col_offset or 0
                idx = seg.find(op, left_end - node.col_offset)
                if idx >= 0:
                    new_seg = seg[:idx] + _FLIP[op] + seg[idx + len(op) :]
                    found.append(
                        _make(
                            "comparison_flip", lines, node, seg, new_seg, f"{op} became {_FLIP[op]}"
                        )
                    )
            for side in (node.left, node.comparators[0]):
                if (
                    isinstance(side, ast.Constant)
                    and isinstance(side.value, int)
                    and not isinstance(side.value, bool)
                ):
                    found.append(_bump(lines, side, "in a comparison"))
        if isinstance(node, ast.Call) and _one_line(node):
            if isinstance(node.func, ast.Name) and node.func.id == "range":
                for arg in node.args:
                    if (
                        isinstance(arg, ast.Constant)
                        and isinstance(arg.value, int)
                        and not isinstance(arg.value, bool)
                    ):
                        found.append(_bump(lines, arg, "in range()"))
            seg = _segment(lines, node)
            if seg.endswith(")"):
                found.append(
                    _make("missing_bracket", lines, node, seg, seg[:-1], "closing bracket removed")
                )
            if isinstance(node.func, ast.Name) and node.func.id == "int" and node.args:
                inner = ast.get_source_segment(source, node.args[0]) or ""
                if "input(" in inner:
                    found.append(
                        _make(
                            "string_int",
                            lines,
                            node,
                            seg,
                            inner,
                            "int() removed: input() gives a string",
                        )
                    )
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, int)
            and not isinstance(node.value, bool)
        ):
            parent_kind = getattr(node, "_tt_parent", None)
            if parent_kind is None:
                pass
        if isinstance(node, ast.If | ast.For | ast.While | ast.FunctionDef | ast.With | ast.Try):
            header = lines[node.lineno - 1]
            if header.rstrip().endswith(":"):
                found.append(
                    Mutation(
                        "missing_colon",
                        node.lineno,
                        header,
                        header.rstrip()[:-1],
                        "colon removed from the header",
                    )
                )
            body = getattr(node, "body", [])
            if body and len(body) > 1:
                last = body[-1]
                text = lines[last.lineno - 1]
                if text.startswith("    ") and _one_line(last):
                    found.append(
                        Mutation(
                            "indentation_slip",
                            last.lineno,
                            text,
                            text[4:],
                            "last line of the block dedented",
                        )
                    )
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names:
            seg_line = lines[node.lineno - 1]
            swap = scope.stand_in(node)
            if swap is not None:
                replacement = swap
                note = f"{node.id} replaced by {replacement}"
            else:  # nothing like it in scope: a misspelling (or a near namesake)
                replacement = node.id[:-1] if len(node.id) > 2 else node.id + "s"
                said = "replaced by" if replacement in names else "misspelt as"
                note = f"{node.id} {said} {replacement}"
            new_line = (
                seg_line[: node.col_offset] + replacement + seg_line[node.end_col_offset or 0 :]
            )
            if new_line != seg_line:
                found.append(Mutation("wrong_variable", node.lineno, seg_line, new_line, note))
        if isinstance(node, ast.BinOp) and _one_line(node):
            for side in (node.left, node.right):
                if (
                    isinstance(side, ast.Constant)
                    and isinstance(side.value, int)
                    and not isinstance(side.value, bool)
                ):
                    line = lines[side.lineno - 1]
                    new_line = (
                        line[: side.col_offset]
                        + f'"{side.value}"'
                        + line[side.end_col_offset or 0 :]
                    )
                    found.append(
                        Mutation(
                            "string_int",
                            side.lineno,
                            line,
                            new_line,
                            f'{side.value} became the string "{side.value}"',
                        )
                    )
    # Only mutations that actually change the line, deduplicated.
    seen: set[tuple[Kind, int, str]] = set()
    unique: list[Mutation] = []
    for m in found:
        key = (m.kind, m.line, m.mutated)
        if m.mutated != m.original and key not in seen:
            seen.add(key)
            unique.append(m)
    return unique


def _assigned_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id not in names:
            names.append(node.id)
    return names


# ---------------------------------------------------------------- wrong_variable stand-ins
# A pupil who types the wrong name usually types one they have just been
# using, of the same sort: ``total`` for ``count``, not the list ``scores``
# for a number. So the stand-in is a name that is already assigned in the
# same scope when the line runs (no NameError) and looks like the same kind
# of value (no TypeError), the most recently assigned first. Both make the
# variant run with the wrong output more often than crash. Kinds are a
# coarse guess from the assignments; anything unclear is "unknown".
_NUMBER_CALLS = {"int", "float", "len", "sum", "round", "abs", "min", "max", "ord"}
_STR_CALLS = {"str", "input", "chr", "repr", "format"}
_LIST_CALLS = {"list", "sorted"}
_SCOPES = ast.Module | ast.FunctionDef | ast.AsyncFunctionDef
# Names bound here live only inside them: never a stand-in for the program's names.
_OWN_NAMES = ast.Lambda | ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp


class _Scopes:
    """Which names each scope assigns, on which lines, and of what kind."""

    def __init__(self, tree: ast.Module) -> None:
        self.stores: dict[ast.AST, dict[str, list[int]]] = {}  # scope -> name -> lines
        self.values: dict[str, list[ast.expr]] = {}  # name -> what it was set to
        self.items: dict[str, list[ast.expr]] = {}  # loop variable -> what it loops over
        self.scope_of: dict[ast.Name, ast.AST] = {}  # every Name -> its scope
        self.globals = tree
        self._walk(tree, tree)
        # Names defined from other names settle in a few passes. Each pass reads
        # only the previous one, so the result does not depend on set order.
        self.kinds: dict[str, str] = {}
        for _ in range(10):
            settled = {name: self._name_kind(name) for name in self.values.keys() | self.items}
            if settled == self.kinds:
                break
            self.kinds = settled

    def _walk(self, node: ast.AST, scope: ast.AST, record: bool = True) -> None:
        for child in ast.iter_child_nodes(node):
            inner = child if isinstance(child, _SCOPES) else scope
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                for a in child.args.posonlyargs + child.args.args + child.args.kwonlyargs:
                    self.stores.setdefault(child, {}).setdefault(a.arg, []).append(child.lineno)
            if isinstance(child, ast.Name):
                self.scope_of[child] = scope
                if record and isinstance(child.ctx, ast.Store):
                    self.stores.setdefault(scope, {}).setdefault(child.id, []).append(child.lineno)
            if isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        self.values.setdefault(target.id, []).append(child.value)
            elif isinstance(child, ast.AnnAssign | ast.AugAssign):
                if isinstance(child.target, ast.Name) and child.value is not None:
                    self.values.setdefault(child.target.id, []).append(child.value)
            elif isinstance(child, ast.For) and isinstance(child.target, ast.Name):
                self.items.setdefault(child.target.id, []).append(child.iter)
            self._walk(child, inner, record and not isinstance(child, _OWN_NAMES))

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
            listed = [v for v in self.values.get(iterable.id, []) if isinstance(v, ast.List)]
            if listed and len(listed) == len(self.values[iterable.id]):
                kinds = {self._kind(e) for v in listed for e in v.elts}
                return kinds.pop() if len(kinds) == 1 else "unknown"
        return "unknown"

    def stand_in(self, use: ast.Name) -> str | None:
        """The name a pupil might plausibly type instead of ``use``, or None."""
        scope = self.scope_of.get(use, self.globals)
        visible = dict(self.stores.get(self.globals, {}))
        if scope is not self.globals:
            visible.update(self.stores.get(scope, {}))
        # Assigned on an earlier line, so it already exists when this line runs.
        earlier = {
            name: max(n for n in at if n < use.lineno)
            for name, at in visible.items()
            if name != use.id and min(at) < use.lineno
        }
        kind = self.kinds.get(use.id, "unknown")
        same = [name for name in earlier if self.kinds.get(name, "unknown") == kind]
        if not same and kind == "unknown":
            same = list(earlier)
        # Most recently assigned before the use; ties in order of appearance.
        return max(same, key=lambda name: earlier[name], default=None)


def _one_line(node: ast.AST) -> bool:
    return getattr(node, "end_lineno", None) == getattr(node, "lineno", None)


def _segment(lines: list[str], node: ast.AST) -> str:
    line = lines[node.lineno - 1]  # type: ignore[attr-defined]
    return line[node.col_offset : node.end_col_offset]  # type: ignore[attr-defined]


def _make(
    kind: Kind, lines: list[str], node: ast.AST, seg: str, new_seg: str, note: str
) -> Mutation:
    line = lines[node.lineno - 1]  # type: ignore[attr-defined]
    start, end = node.col_offset, node.end_col_offset  # type: ignore[attr-defined]
    return Mutation(kind, node.lineno, line, line[:start] + new_seg + line[end:], note)  # type: ignore[attr-defined]


def _bump(lines: list[str], const: ast.Constant, where: str) -> Mutation:
    line = lines[const.lineno - 1]
    value = const.value
    assert isinstance(value, int)
    new = value + 1 if value % 2 == 0 else value - 1
    new_line = line[: const.col_offset] + str(new) + line[const.end_col_offset or 0 :]
    return Mutation("off_by_one", const.lineno, line, new_line, f"{value} became {new} {where}")


# ---------------------------------------------------------------- choosing and applying
# What a variant does when it runs, as the caller's sandbox run found it.
# "syntax_error" covers every error Python reports before the program starts
# (SyntaxError, IndentationError, TabError).
Outcome = Literal["wrong_output", "crash", "syntax_error", "hang", "silent"]
SYNTAX_ERRORS_PER_SHEET = 1  # more only when nothing else makes up the count


def choose(
    source: str,
    count: int,
    kinds: list[Kind],
    seed: int,
    outcome_of: Callable[[Mutation], Outcome | bool] | None = None,
    silent: int = 0,
) -> list[Mutation]:
    """Pick up to ``count`` mutations of the enabled kinds, spreading across
    kinds and lines and aiming for a mix of outcomes, deterministically for a
    seed.

    ``outcome_of`` (supplied by the caller, which runs the variant in the
    sandbox) says what a mutation does when the program runs. It may answer
    with a bare bool (True: visible, False: silent) when only silence
    matters; then no mix is aimed for. Candidates are tried in the seed's
    order and each is judged at most once:

    * a silent one is taken only while fewer than ``silent`` have been kept;
    * a second SyntaxError is held back, and used only if nothing else is
      left to make up the count;
    * with two or more variants and no wrong-output bug among them, the
      first wrong-output candidate in the seed's order replaces the last of
      the most common outcome (never a kept silent one).

    Without the callback every candidate counts as visible. Fewer than
    ``count`` come back when the candidates run out."""
    rng = random.Random(seed)
    pool = [m for m in candidates(source) if m.kind in kinds]
    rng.shuffle(pool)
    kind_order = list(kinds)
    rng.shuffle(kind_order)
    chosen: list[Mutation] = []
    used_lines: set[int] = set()
    verdicts: dict[Mutation, Outcome | None] = {}  # None: visible, outcome unknown
    held_back: list[Mutation] = []  # SyntaxErrors past the per-sheet allowance
    silent_left = silent

    def verdict(m: Mutation) -> Outcome | None:
        if outcome_of is None:
            return None
        if m not in verdicts:
            said = outcome_of(m)
            verdicts[m] = (None if said else "silent") if isinstance(said, bool) else said
        return verdicts[m]

    def accept(m: Mutation) -> bool:
        nonlocal silent_left
        v = verdict(m)
        if v == "silent":
            if silent_left > 0:
                silent_left -= 1
                return True
            return False
        if v == "syntax_error":
            syntax = sum(verdicts.get(c) == "syntax_error" for c in chosen)
            if syntax >= SYNTAX_ERRORS_PER_SHEET:
                if m not in held_back:
                    held_back.append(m)
                return False
        return True

    # One per kind first, on a fresh line where possible; then fill up.
    for kind in kind_order:
        if len(chosen) >= count:
            break
        of_kind = [m for m in pool if m.kind == kind and m not in chosen]
        fresh_first = sorted(of_kind, key=lambda m: m.line in used_lines)  # stable
        pick = next((m for m in fresh_first if accept(m)), None)
        if pick is not None:
            chosen.append(pick)
            used_lines.add(pick.line)
    for m in pool:
        if len(chosen) >= count:
            break
        if m not in chosen and accept(m):
            chosen.append(m)
            used_lines.add(m.line)
    # Extra SyntaxErrors only to make up the count.
    for m in held_back:
        if len(chosen) >= count:
            break
        chosen.append(m)
        used_lines.add(m.line)

    # At least one "runs, but the output is wrong" when the program has one.
    if (
        count >= 2
        and len(chosen) >= 2
        and _knows_outcomes(chosen, verdicts)
        and not any(verdicts[c] == "wrong_output" for c in chosen)
    ):
        victim = _give_way(chosen, verdicts)
        rest = [m for m in pool if m not in chosen] if victim is not None else []
        fresh_first = sorted(rest, key=lambda m: m.line in used_lines)  # stable
        wrong = next((m for m in fresh_first if verdict(m) == "wrong_output"), None)
        if wrong is not None and victim is not None:
            chosen[victim] = wrong
    return chosen


def _knows_outcomes(chosen: list[Mutation], verdicts: dict[Mutation, Outcome | None]) -> bool:
    """True when the caller judged outcomes, not just silence."""
    return all(verdicts.get(c) is not None for c in chosen)


def _give_way(chosen: list[Mutation], verdicts: dict[Mutation, Outcome | None]) -> int | None:
    """Index of the variant to swap for a wrong-output one: the last of the
    most common outcome. Kept silent ones were asked for, so never them."""
    tally: dict[Outcome | None, int] = {}
    for c in chosen:
        tally[verdicts[c]] = tally.get(verdicts[c], 0) + 1
    swappable = [i for i, c in enumerate(chosen) if verdicts[c] != "silent"]
    if not swappable:
        return None
    return max(reversed(swappable), key=lambda i: tally[verdicts[chosen[i]]])


def apply(source: str, mutation: Mutation) -> str:
    lines = source.splitlines(keepends=True)
    original = lines[mutation.line - 1]
    newline = "\n" if original.endswith("\n") else ""
    assert original.rstrip("\n") == mutation.original, "source changed since the mutation was found"
    lines[mutation.line - 1] = mutation.mutated + newline
    return "".join(lines)


def make_variants(
    source: str,
    options: Options,
    outcome_of: Callable[[Mutation], Outcome | bool] | None = None,
) -> list[Variant]:
    """The variants for ``options``; see :func:`choose` for ``outcome_of``."""
    chosen = choose(
        source, options.count, options.kinds(), options.seed, outcome_of, options.silent
    )
    return [Variant(i, m, apply(source, m)) for i, m in enumerate(chosen, 1)]


# ---------------------------------------------------------------- the key's two lines
SPACE_MARK, TAB_MARK = "·", "»"  # both in Latin-1, so the PDF's Courier has them
INDENT_LEGEND = f"{SPACE_MARK} marks one space of indentation."


def key_lines(mutation: Mutation) -> tuple[str, str]:
    """The "Original" and "Changed to" text for the key.

    Leading whitespace is normally trimmed, but when the bug *is* the
    indentation the two lines would then read the same: there each space of
    indentation shows as a ``·`` (a tab as ``»``) so the change can be seen."""
    old, new = mutation.original.rstrip(), mutation.mutated.rstrip()
    if _indent(old) == _indent(new):
        return old.strip(), new.strip()
    return _show_indent(old), _show_indent(new)


def key_label(mutation: Mutation) -> str:
    """The "Bug" text for the key: the kind, and for a change of indentation
    how far it moved, since a ``·`` is easy to miss in a proportional font."""
    old, new = len(_indent(mutation.original)), len(_indent(mutation.mutated))
    if old == new:
        return mutation.label
    return f"{mutation.label} ({old} {'space' if old == 1 else 'spaces'} to {new})"


def shows_indent(rows: list[tuple[str, str]]) -> bool:
    """Does any (original, changed) pair use the indentation marks?"""
    return any(o != o.lstrip(SPACE_MARK + TAB_MARK) for pair in rows for o in pair)


def _indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _show_indent(line: str) -> str:
    lead = _indent(line)
    return lead.replace(" ", SPACE_MARK).replace("\t", TAB_MARK) + line[len(lead) :]


def one_line_diff(a: str, b: str) -> tuple[int, str, str] | None:
    """``(line_no, old, new)`` if exactly one line differs, else None."""
    la, lb = a.splitlines(), b.splitlines()
    if len(la) != len(lb):
        return None
    diffs = [(i + 1, x, y) for i, (x, y) in enumerate(zip(la, lb, strict=True)) if x != y]
    return diffs[0] if len(diffs) == 1 else None


_WS = re.compile(r"\s+")


def describes(mutation: Mutation, old: str, new: str) -> bool:
    """Does the (old, new) line pair match the mutation's kind?"""
    o, n = _WS.sub(" ", old.strip()), _WS.sub(" ", new.strip())
    if mutation.kind == "missing_colon":
        return o.endswith(":") and n == o[:-1]
    if mutation.kind == "missing_bracket":
        return o.count(")") == n.count(")") + 1 and o.count("(") == n.count("(")
    if mutation.kind == "indentation_slip":
        return (
            old.strip() == new.strip()
            and len(old) - len(old.lstrip()) == len(new) - len(new.lstrip()) + 4
        )
    if mutation.kind == "comparison_flip":
        return any(op in o for op in _FLIP) and o != n and len(o) - len(n) in (-1, 0, 1)
    if mutation.kind == "off_by_one":
        return len(re.findall(r"\d+", o)) == len(re.findall(r"\d+", n)) and o != n
    if mutation.kind == "wrong_variable":
        return o != n and re.sub(r"[A-Za-z_]\w*", "x", o) == re.sub(r"[A-Za-z_]\w*", "x", n)
    if mutation.kind == "string_int":
        return ("int(" in o and "int(" not in n) or (n.count('"') == o.count('"') + 2)
    return False
