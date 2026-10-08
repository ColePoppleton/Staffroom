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


DEFAULT_ORDER = 1000
"""Sidebar position for a plugin that declares no ``order``: after every tool
that does, alphabetically."""


@runtime_checkable
class ToolPlugin(Protocol):
    """Required: ``name``, ``description``, ``version`` and the three methods.

    Optional class attributes the host also reads (both are read with
    ``getattr`` so a plugin without them needs no change):

    * ``order: int`` places the tool in the sidebar and the ``⌘1``-``⌘9``
      shortcuts; lower comes first, ties break by name. Without it the tool
      sits after every ordered one (see :func:`plugin_order`).
    * ``hidden: bool`` keeps the tool out of the launcher sidebar and the
      number shortcuts. It still loads, still has its ``staff <name>`` commands,
      and ``staff list`` shows it with a marker. For reference and developer
      tools, not for anything a teacher should find.
    """

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


def plugin_order(plugin: ToolPlugin) -> int:
    """The plugin's declared ``order``, or :data:`DEFAULT_ORDER`."""
    value = getattr(plugin, "order", None)
    return value if isinstance(value, int) and not isinstance(value, bool) else DEFAULT_ORDER


def plugin_hidden(plugin: ToolPlugin) -> bool:
    """True when the plugin declares ``hidden = True``."""
    return bool(getattr(plugin, "hidden", False))
