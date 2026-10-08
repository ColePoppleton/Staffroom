"""Code for a tool to work on: a picked file or pasted text.

Several tools share the same two inputs, a ``ResourcePicker`` (key
``source``) and a ``TextArea`` (key ``pasted``). This resolves them the same
way everywhere: the file wins, then pasted text, else a
:class:`~staffroom.core.plugin.ToolError` for the teacher."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from staffroom.core.plugin import ToolError


def code_from_inputs(
    inputs: Mapping[str, Any], *, picker_key: str = "source", pasted_key: str = "pasted"
) -> tuple[str, str]:
    """Return ``(source, name)``. Raises :class:`ToolError` with a one-line
    message for the teacher when there is no code or the file cannot be read."""
    path = inputs.get(picker_key)
    if isinstance(path, Path):
        try:
            return path.read_text(encoding="utf-8", errors="replace"), path.stem
        except FileNotFoundError:
            raise ToolError(f"Could not find {path.name} (looked in {path.parent}).") from None
        except OSError as exc:
            reason = exc.strerror or exc.__class__.__name__
            raise ToolError(f"Could not read {path.name}: {reason}.") from exc
    pasted = str(inputs.get(pasted_key) or "")
    if pasted.strip():
        return pasted, "pasted_code"
    raise ToolError("Choose a Python file or paste some code.")


def numbered_listing(source: str) -> str:
    lines = source.rstrip("\n").splitlines()
    width = len(str(len(lines)))
    return "\n".join(f"{i:>{width}}  {line}" for i, line in enumerate(lines, 1))
