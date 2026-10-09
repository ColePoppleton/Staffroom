"""Code for a tool to work on: a picked file or pasted text.

The one place that turns a code tool's input into source text. The panel
gives a :class:`~staffroom.core.panel.CodeValue` (key ``source``) from its
``CodeSource``; the command line and older callers give a ``Path`` under
``source`` and/or pasted text under ``pasted``. Either way: the file wins
(read afresh, so an edit saved in Thonny since it was picked counts), then
pasted text, else a :class:`~staffroom.core.plugin.ToolError` for the
teacher."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from staffroom.core.panel import CodeValue
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
