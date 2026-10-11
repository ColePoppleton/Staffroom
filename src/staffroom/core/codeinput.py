"""Code for a tool to work on: a picked file or pasted text.

The one place that turns a code tool's input into source text. The panel
gives a :class:`~staffroom.core.panel.CodeValue` (key ``source``) from its
``CodeSource``; the command line and older callers give a ``Path`` under
``source`` and/or pasted text under ``pasted``. Either way: the file wins
(read afresh, so an edit saved in Thonny since it was picked counts), then
pasted text, else a :class:`~staffroom.core.plugin.ToolError` for the
teacher."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from staffroom.core.panel import CodeValue, Inspection
from staffroom.core.plugin import ToolError

PASTED_NAME = "pasted_code"


def code_path(inputs: Mapping[str, Any], *, picker_key: str = "source") -> Path | None:
    """The file the code comes from, if it comes from one."""
    value = inputs.get(picker_key)
    if isinstance(value, CodeValue):
        return value.path
    return value if isinstance(value, Path) else None


def read_code_file(path: Path) -> str:
    """The file's text. Raises :class:`ToolError` with a one-line message."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise ToolError(f"Could not find {path.name} (looked in {path.parent}).") from None
    except OSError as exc:
        reason = exc.strerror or exc.__class__.__name__
        raise ToolError(f"Could not read {path.name}: {reason}.") from exc


def code_from_inputs(
    inputs: Mapping[str, Any], *, picker_key: str = "source", pasted_key: str = "pasted"
) -> tuple[str, str]:
    """Return ``(source, name)``. Raises :class:`ToolError` with a one-line
    message for the teacher when there is no code or the file cannot be read."""
    path = code_path(inputs, picker_key=picker_key)
    if path is not None:
        return read_code_file(path), path.stem
    value = inputs.get(picker_key)
    pasted = value.text if isinstance(value, CodeValue) else str(inputs.get(pasted_key) or "")
    if pasted.strip():
        return pasted, PASTED_NAME
    raise ToolError("Choose a Python file or paste some code.")


def numbered_listing(source: str) -> str:
    lines = source.rstrip("\n").splitlines()
    width = len(str(len(lines)))
    return "\n".join(f"{i:>{width}}  {line}" for i, line in enumerate(lines, 1))


# ---------------------------------------------------------------- input() calls
INPUTS_PLACEHOLDER = "One line per input() call"
"""An Inputs box's placeholder before there is code to count in."""


@dataclass(frozen=True)
class InputCalls:
    """How many times a program's code calls ``input()``, read statically.

    ``count`` is the number of ``input(...)`` calls written in the code.
    ``repeats`` says where one of them sits that can run more than once (or
    not at all): ``"loop"`` (a ``for``/``while`` body or a comprehension),
    ``"function"`` (a ``def`` or ``lambda`` body), or ``""`` when every call
    is at the top level and the count is the number of lines the program
    reads (counting both arms of an ``if``)."""

    count: int
    repeats: Literal["", "loop", "function"] = ""

    @property
    def at_least(self) -> bool:
        return bool(self.repeats)


_LOOPS = (
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
)
_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)


def count_input_calls(source: str) -> InputCalls | None:
    """The ``input()`` calls in ``source``; None if it is not valid Python."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return None
    count = 0
    in_loop = in_function = False

    def visit(node: ast.AST, loop: bool, function: bool) -> None:
        nonlocal count, in_loop, in_function
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "input"
        ):
            count += 1
            in_loop = in_loop or loop
            in_function = in_function or function
        loop = loop or isinstance(node, _LOOPS)
        function = function or isinstance(node, _FUNCTIONS)
        for child in ast.iter_child_nodes(node):
            visit(child, loop, function)

    visit(tree, False, False)
    repeats: Literal["", "loop", "function"] = (
        "loop" if in_loop else "function" if in_function else ""
    )
    return InputCalls(count, repeats)


def input_calls_phrase(calls: InputCalls) -> str:
    """How often the code calls ``input()``, for a sentence: "once", "3 times",
    "at least 2 times (one is in a loop)"."""
    if calls.at_least:
        return f"at least {_times(calls.count)} (one is in a {calls.repeats})"
    return _times(calls.count)


def _times(n: int) -> str:
    return "once" if n == 1 else "twice" if n == 2 else f"{n} times"


def inputs_placeholder(source: str) -> str:
    """The Inputs box's placeholder for ``source``: how many lines it reads,
    as far as the code shows (#21). Two short lines, to fit the box."""
    calls = count_input_calls(source)
    if calls is None:
        return INPUTS_PLACEHOLDER
    n = calls.count
    if n == 0:
        return "No input() calls in this program:\nleave this empty"
    if calls.at_least:
        calls_word = "call" if n == 1 else "calls"
        return f"At least {n} input() {calls_word}\n(in a {calls.repeats}): one line each"
    if n == 1:
        return "1 input() call:\none line"
    return f"{n} input() calls:\none line each"


def inspect_inputs_box(inputs: Mapping[str, Any], *, stdin_key: str = "stdin") -> Inspection:
    """``PanelSpec.inspect`` for a code tool with an Inputs box: the box's
    placeholder counts the program's ``input()`` calls. No code (or a file
    that cannot be read) keeps the panel's own placeholder."""
    try:
        source, _name = code_from_inputs(inputs)
    except ToolError:
        return Inspection()
    return Inspection(placeholders={stdin_key: inputs_placeholder(source)})
