"""Pure logic for trace: classify lines, build the tables. No I/O."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Literal

from staffroom.core.codeinput import InputCalls, input_calls_phrase
from staffroom.core.panel import OptionsPreset, matching_preset, preset
from staffroom.core.table import Row, Table

Kind = Literal["assign", "loop", "if", "call", "other"]
TIMEOUT = 10.0  # seconds a traced run may take; the panel description quotes it
CUSTOM = "Custom"  # what the sheet says when the options match no preset


@dataclass
class Options:
    max_steps: int = field(default=60, metadata={"label": "Max steps", "min": 1, "max": 2000})
    assignments: bool = field(default=True, metadata={"label": "Record assignments"})
    loops: bool = field(default=True, metadata={"label": "Record loop headers"})
    ifs: bool = field(default=True, metadata={"label": "Record if / elif"})
    calls: bool = field(default=True, metadata={"label": "Record calls (print, input…)"})
    top_level_only: bool = field(
        default=False,
        metadata={
            "label": "Top-level variables only",
            "help": (
                "Leave out the lines run inside functions and their local variables, "
                "so the table has no Scope column. The Year 9 preset turns this on."
            ),
        },
    )
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


# What a preset pins: every setting that shapes the table. Steps and output
# format are left to the teacher, so changing them keeps the preset's name.
_TABLE_SHAPE = {"assignments": True, "loops": True, "ifs": True, "calls": True, "variables": ""}
PRESETS: tuple[OptionsPreset, ...] = (
    preset("Full trace", top_level_only=False, **_TABLE_SHAPE),
    preset("Year 9", top_level_only=True, **_TABLE_SHAPE),
)


def preset_name(options: Options) -> str:
    """The preset these options amount to, for the sheet header: "Full trace",
    "Year 9" or "Custom". Decided from the values, not the dropdown, so the CLI
    and a hand-edited form agree with what is printed."""
    match = matching_preset(PRESETS, options)
    return match.name if match else CUSTOM


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
    input_eof: bool = False  # the run ended because input() found nothing left to read
    inputs_read: int = 0  # values input() had read by then


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
        input_eof=bool(payload.get("input_eof")),
        inputs_read=int(payload.get("inputs_read", 0)),
    )


def program_label(name: str) -> str:
    """How a message refers to the program: its file name, or the pasted code."""
    return "The pasted code" if name == "pasted_code" else f"{name}.py"


def missing_input_message(name: str, stdin: str, inputs_read: int) -> str:
    """What went wrong in a run that hit ``input()`` with nothing left to
    read, in words for the strip and the CLI alike (where to type the inputs
    differs, so it is the next step's job: :func:`missing_input_step`,
    :func:`stdin_option_step`). ``stdin`` is what the run was given."""
    given = len(stdin.splitlines())
    if given == 0:
        return f"{program_label(name)} asked for input, but none was given."
    return (
        f"{program_label(name)} asked for a {_ordinal(inputs_read + 1)} input, "
        f"but was given only {_lines(given)}."
    )


def lines_needed(calls: InputCalls | None, inputs_read: int) -> str:
    """How many lines of input the program needs, as far as its code and the
    run show: "1 line", "2 lines", or "at least 3 lines" when a call can
    repeat or the run asked for more than the code's count."""
    asked = inputs_read + 1
    if calls is None or calls.at_least or calls.count < asked:
        return "at least " + _lines(max(asked, calls.count if calls else 0))
    return _lines(calls.count)


def missing_input_step(name: str, calls: InputCalls | None, needed: str) -> str:
    """The launcher's next step after a missing input, shown in the output
    pane: how often the code asks, and what to type where."""
    step = f"Type {needed} in the Inputs box, then press Trace again."
    if calls is None or not calls.count:
        return step
    return f"{program_label(name)} calls input() {input_calls_phrase(calls)}. {step}"


def missing_input_hint(needed: str) -> str:
    """The line under the marked Inputs box."""
    return f"Needs {needed}, one per input() call."


def stdin_option_step(needed: str) -> str:
    """The CLI's next step after a missing input: it names ``--stdin``."""
    return (
        f"Give it {needed} with --stdin, one per input() call; "
        'separate lines with \\n, as in --stdin "12\\n7".'
    )


def _lines(n: int) -> str:
    return "1 line" if n == 1 else f"{n} lines"


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def select_steps(
    result: TraceResult, source: str, kinds: set[Kind], *, top_level_only: bool = False
) -> list[Step]:
    """The steps to record: those whose line is one of ``kinds`` and, with
    ``top_level_only``, those run at module level (a step inside a function
    carries its function's name as ``scope``)."""
    by_line = line_kinds(source)
    return [
        s
        for s in result.steps
        if by_line.get(s.line, "other") in kinds and not (top_level_only and s.scope)
    ]


def chosen_variables(
    result: TraceResult, wanted: str, steps: list[Step] | None = None
) -> list[str]:
    """The columns: the names in ``wanted`` (comma-separated) if any, else every
    variable the run touched, in first-seen order. With ``steps``, only variables
    that appear in one of those steps, so dropping function scopes drops their
    locals too."""
    available = result.variables
    if steps is not None:
        available = [v for v in available if any(v in s.values for s in steps)]
    if wanted.strip():
        names = [n.strip() for n in wanted.split(",") if n.strip()]
        return [n for n in names if n in available] or names
    return list(available)


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
