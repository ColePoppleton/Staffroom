"""The tracer that runs *inside the sandbox child*, not in the app.

Usage (by the runner): ``python tt_tracer.py program.py MAX_STEPS``.
It executes ``program.py`` under ``sys.settrace`` and prints one JSON object
to the real stdout: rows of executed lines with the variable values after
each line and any output printed by it. Only frames from ``program.py`` are
recorded; everything the program prints is captured, not shown.
"""

from __future__ import annotations

import io
import json
import sys
import traceback
from types import FrameType
from typing import Any

MAX_REPR = 48


def show(value: Any) -> str | None:
    """A printable value, or None for things that do not belong in a trace
    table (modules, functions, classes)."""
    if callable(value) and not isinstance(value, type):
        return None
    if isinstance(value, type) or type(value).__name__ == "module":
        return None
    text = repr(value)
    return text if len(text) <= MAX_REPR else text[: MAX_REPR - 1] + "…"


def main() -> None:
    program, max_steps = sys.argv[1], int(sys.argv[2])
    with open(program, encoding="utf-8") as fh:
        source = fh.read()
    code = compile(source, program, "exec")
    real_stdout = sys.stdout
    captured = io.StringIO()
    sys.stdout = captured
    rows: list[dict[str, Any]] = []
    pending: dict[int, dict[str, Any]] = {}  # id(frame) -> row awaiting its "after" state
    variables: list[str] = []
    state = {"steps": 0, "truncated": False}
    last_output_pos = 0

    def take_output() -> str:
        nonlocal last_output_pos
        text = captured.getvalue()
        chunk = text[last_output_pos:]
        last_output_pos = len(text)
        return chunk

    def snapshot(frame: FrameType) -> dict[str, str]:
        values: dict[str, str] = {}
        for name, value in frame.f_locals.items():
            if name.startswith("__"):
                continue
            text = show(value)
            if text is None:
                continue
            values[name] = text
            if name not in variables:
                variables.append(name)
        return values

    def finalise(frame: FrameType) -> None:
        row = pending.pop(id(frame), None)
        if row is not None:
            row["vars"] = snapshot(frame)
            row["output"] = take_output()

    def tracer(frame: FrameType, event: str, arg: Any) -> Any:
        if frame.f_code.co_filename != program:
            return None
        if event == "call":
            return tracer
        if event == "line":
            finalise(frame)
            if state["steps"] >= max_steps:
                state["truncated"] = True
                sys.settrace(None)
                return None
            state["steps"] += 1
            scope = "" if frame.f_code.co_name == "<module>" else frame.f_code.co_name
            row: dict[str, Any] = {"line": frame.f_lineno, "scope": scope, "vars": {}, "output": ""}
            rows.append(row)
            pending[id(frame)] = row
        elif event == "return":
            finalise(frame)
        return tracer

    error = None
    namespace: dict[str, Any] = {"__name__": "__main__", "__file__": program}
    sys.settrace(tracer)
    try:
        exec(code, namespace)
    except BaseException:
        error = traceback.format_exc(limit=-1).strip().splitlines()[-1]
    finally:
        sys.settrace(None)
        sys.stdout = real_stdout
    # Any rows still pending (e.g. after an exception) get the final state.
    for row in list(pending.values()):
        row["output"] = take_output()
    payload = {
        "rows": rows,
        "variables": variables,
        "truncated": state["truncated"],
        "error": error,
        "stdout": captured.getvalue(),
    }
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
