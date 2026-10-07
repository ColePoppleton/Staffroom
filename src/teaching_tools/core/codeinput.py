"""Code for a tool to work on: a picked file or pasted text.

Several tools share the same two inputs, a ``ResourcePicker`` (key
``source``) and a ``TextArea`` (key ``pasted``). This resolves them the same
way everywhere: the file wins, then pasted text, else an error for the
teacher."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any


def code_from_inputs(
    inputs: Mapping[str, Any], *, picker_key: str = "source", pasted_key: str = "pasted"
) -> tuple[str, str]:
    """Return ``(source, name)``. Raises ValueError with a user-facing message."""
    path = inputs.get(picker_key)
    if isinstance(path, Path):
        try:
            return path.read_text(encoding="utf-8", errors="replace"), path.stem
        except OSError as exc:
            msg = f"Could not read {path}: {exc}"
            raise ValueError(msg) from exc
    pasted = str(inputs.get(pasted_key) or "")
    if pasted.strip():
        return pasted, "pasted_code"
    msg = "Choose a Python file or paste some code."
    raise ValueError(msg)


def numbered_listing(source: str) -> str:
    lines = source.rstrip("\n").splitlines()
    width = len(str(len(lines)))
    return "\n".join(f"{i:>{width}}  {line}" for i, line in enumerate(lines, 1))
