"""Pure logic for trace: classify lines, build the tables. No I/O."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Literal

from teaching_tools.core.table import Row, Table

Kind = Literal["assign", "loop", "if", "call", "other"]


@dataclass
class Options:
    max_steps: int = field(default=60, metadata={"label": "Max steps", "min": 1, "max": 2000})
    assignments: bool = field(default=True, metadata={"label": "Record assignments"})
    loops: bool = field(default=True, metadata={"label": "Record loop headers"})
    ifs: bool = field(default=True, metadata={"label": "Record if / elif"})
    calls: bool = field(default=True, metadata={"label": "Record calls (print, input…)"})
    variables: str = field(
        default="",
        metadata={
            "label": "Variables",
            "help": "Comma-separated to limit the columns; empty = all",
        },
    )
    blank_line_numbers: bool = field(
        default=True, metadata={"label": "Blank sheet shows line numbers"}
    )
    formats: Literal["both", "docx", "pdf"] = field(default="both", metadata={"label": "Output"})

    def kinds(self) -> set[Kind]:
        chosen: set[Kind] = set()
        if self.assignments:
            chosen.add("assign")
        if self.loops:
            chosen.add("loop")
        if self.ifs:
            chosen.add("if")
        if self.calls:
            chosen.add("call")
        return chosen


@dataclass(frozen=True)
class Step:
    line: int
    scope: str
    values: dict[str, str]
    output: str


@dataclass
class TraceResult:
    steps: list[Step]
    variables: list[str]
    truncated: bool
    error: str | None
    stdout: str


def line_kinds(source: str) -> dict[int, Kind]:
    """What each line of code *is*, for the recording filter."""
    kinds: dict[int, Kind] = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return kinds
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        kind: Kind = "other"
        if isinstance(node, ast.Assign | ast.AugAssign | ast.AnnAssign):
            kind = "assign"
        elif isinstance(node, ast.For | ast.While):
            kind = "loop"
        elif isinstance(node, ast.If):
            kind = "if"
        elif (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)) or (
            isinstance(node, ast.Return) and node.value is not None
        ):
            kind = "call"
        # A compound statement only owns its header line(s); its body
        # statements classify themselves.
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.stmt):
            last = body[0].lineno - 1
        else:
            last = node.end_lineno or node.lineno
        for lineno in range(node.lineno, last + 1):
            kinds.setdefault(lineno, kind)
    return kinds


def parse_payload(payload: dict[str, Any]) -> TraceResult:
    steps = [
        Step(
            int(r["line"]),
            str(r.get("scope", "")),
            dict(r.get("vars", {})),
            str(r.get("output", "")),
        )
        for r in payload.get("rows", [])
    ]
    return TraceResult(
        steps=steps,
        variables=[str(v) for v in payload.get("variables", [])],
        truncated=bool(payload.get("truncated")),
        error=payload.get("error"),
        stdout=str(payload.get("stdout", "")),
    )


def select_steps(result: TraceResult, source: str, kinds: set[Kind]) -> list[Step]:
    by_line = line_kinds(source)
    return [s for s in result.steps if by_line.get(s.line, "other") in kinds]


def chosen_variables(result: TraceResult, wanted: str) -> list[str]:
    if wanted.strip():
        names = [n.strip() for n in wanted.split(",") if n.strip()]
        return [n for n in names if n in result.variables] or names
    return list(result.variables)


def trace_table(
    steps: list[Step], variables: list[str], *, blank: bool = False, line_numbers: bool = True
) -> Table:
    """Columns: Line, Scope (if any function ran), each variable, Output.
    A blank table keeps the shape (and, by default, the line numbers)."""
    scoped = any(s.scope for s in steps)
    columns = ["Line", *(["Scope"] if scoped else []), *variables, "Output"]
    rows: list[Row] = []
    for s in steps:
        row: Row = [s.line if (line_numbers or not blank) else None]
        if scoped:
            row.append(s.scope if not blank else None)
        for v in variables:
            row.append(None if blank else s.values.get(v, ""))
        row.append(None if blank else s.output.rstrip("\n").replace("\n", " ⏎ "))
        rows.append(row)
    return Table(columns, rows)
