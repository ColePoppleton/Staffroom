"""The plugin contract every tool package fulfils.

A tool package exposes a module-level ``plugin`` object satisfying
:class:`ToolPlugin`. The shell and CLI only ever talk to tools through this
protocol, :class:`RunContext` and :class:`RunResult`.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from staffroom.core.config import Config
from staffroom.core.library.service import ResourceService
from staffroom.core.panel import PanelSpec
from staffroom.core.table import Table

Inputs = Mapping[str, Any]


class ToolError(Exception):
    """Raised by a tool for a user-facing failure (bad input, missing column).
    The shell shows the message; anything else is treated as a bug."""


@dataclass
class RunResult:
    """What a run produced. Keys match the panel's output widgets."""

    tables: dict[str, Table] = field(default_factory=dict)
    images: dict[str, Path] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    files: list[Path] = field(default_factory=list)
    summary: str = ""


@dataclass
class RunContext:
    """Services the host gives a running tool. ``progress`` takes a fraction in
    [0, 1] and a short message; ``log`` sends a line to the log area."""

    config: Config
    output_dir: Path
    progress: Callable[[float, str], None] = lambda _f, _m: None
    log: Callable[[str], None] = lambda _m: None
    resources: ResourceService | None = None  # the Resource Library, when the host has one

    def note_run(self, tool: str) -> None:
        """Record that ``tool`` ran (for the usage review). Hosts call this;
        the shell does it in its worker, CLIs after a successful run."""
        from staffroom.core.usage import record_run

        record_run(tool)


@runtime_checkable
class ToolPlugin(Protocol):
    name: str
    description: str
    version: str

    def register_cli(self, app: Any) -> None:
        """Attach commands to the tool's typer sub-app (``staff <name> ...``)."""

    def panel_spec(self) -> PanelSpec:
        """Declare the tool's UI."""

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        """Execute with the values gathered from the panel's input widgets."""


@runtime_checkable
class SupportsActions(Protocol):
    """Optional: a plugin whose panel has ``ActionTable`` widgets."""

    def act(self, name: str, row: Mapping[str, Any], ctx: RunContext) -> RunResult:
        """Perform ``name`` on ``row`` (empty for a refresh action)."""
