"""Pure logic for bugs: find places a controlled error can be injected and
apply exactly one per variant. No I/O."""

from __future__ import annotations

import ast
import random
import re
from dataclasses import dataclass, field
from typing import Literal

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


# ---------------------------------------------------------------- candidates
def candidates(source: str) -> list[Mutation]:
    """Every single-line mutation the program admits, across all kinds."""
    tree = ast.parse(source)
    lines = source.splitlines()
    found: list[Mutation] = []
    names = _assigned_names(tree)

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
            others = [n for n in names if n != node.id]
            seg_line = lines[node.lineno - 1]
            if others:
                replacement = others[0]
                note = f"{node.id} replaced by {replacement}"
            else:
                replacement = node.id[:-1] if len(node.id) > 2 else node.id + "s"
                note = f"{node.id} misspelt as {replacement}"
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
def choose(source: str, count: int, kinds: list[Kind], seed: int) -> list[Mutation]:
    """Pick up to ``count`` mutations of the enabled kinds, spreading across
    kinds and lines, deterministically for a seed."""
    rng = random.Random(seed)
    pool = [m for m in candidates(source) if m.kind in kinds]
    rng.shuffle(pool)
    kind_order = list(kinds)
    rng.shuffle(kind_order)
    chosen: list[Mutation] = []
    used_lines: set[int] = set()
    # One per kind first, on a fresh line where possible; then fill up.
    for kind in kind_order:
        if len(chosen) >= count:
            break
        of_kind = [m for m in pool if m.kind == kind and m not in chosen]
        pick = next((m for m in of_kind if m.line not in used_lines), None) or (
            of_kind[0] if of_kind else None
        )
        if pick is not None:
            chosen.append(pick)
            used_lines.add(pick.line)
    for m in pool:
        if len(chosen) >= count:
            break
        if m not in chosen:
            chosen.append(m)
    return chosen


def apply(source: str, mutation: Mutation) -> str:
    lines = source.splitlines(keepends=True)
    original = lines[mutation.line - 1]
    newline = "\n" if original.endswith("\n") else ""
    assert original.rstrip("\n") == mutation.original, "source changed since the mutation was found"
    lines[mutation.line - 1] = mutation.mutated + newline
    return "".join(lines)


def make_variants(source: str, options: Options) -> list[Variant]:
    chosen = choose(source, options.count, options.kinds(), options.seed)
    return [Variant(i, m, apply(source, m)) for i, m in enumerate(chosen, 1)]


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
