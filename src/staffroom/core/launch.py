"""Launch the teacher's editor on a file.

The command is a template such as ``open -a Thonny {file}``; ``{file}`` is
replaced token-wise after shell-style splitting, so paths with spaces are
safe. Presets cover Thonny (the classroom editor), IDLE and the system
default; anything else is a custom command.
"""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

Runner = Callable[[Sequence[str]], None]

DEFAULT_EDITOR = "open -a Thonny {file}"

EDITOR_PRESETS: dict[str, str] = {
    "Thonny": DEFAULT_EDITOR,
    "IDLE": "python3 -m idlelib {file}",
    "System default": "open {file}",
}


def preset_for(command: str) -> str:
    for name, cmd in EDITOR_PRESETS.items():
        if cmd == command.strip():
            return name
    return "Custom"


def editor_argv(command: str, file: Path) -> list[str]:
    tokens = shlex.split(command.strip() or DEFAULT_EDITOR)
    if not any("{file}" in t for t in tokens):
        tokens.append("{file}")
    return [t.replace("{file}", str(file)) for t in tokens]


def _popen(argv: Sequence[str]) -> None:
    subprocess.Popen(list(argv))


def launch_editor(command: str, file: Path, runner: Runner | None = None) -> list[str]:
    """Start the editor detached and return the argv used. ``runner`` defaults
    to a detached subprocess, looked up at call time so tests can intercept it."""
    argv = editor_argv(command, file)
    (runner or _popen)(argv)
    return argv
