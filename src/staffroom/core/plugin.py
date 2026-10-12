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
from staffroom.core.panel import Pages, PanelSpec
from staffroom.core.table import Table

Inputs = Mapping[str, Any]


class ToolError(Exception):
    """Raised by a tool for a user-facing failure (bad input, missing column).
    The shell shows the message; anything else is treated as a bug.

    The message says what went wrong, in one line, and is all a CLI prints.
    In the launcher the message is the result strip's red line, and three
    optional fields say what to do about it (#21):

    * ``next_step``: a sentence that takes the output pane's place until the
      next run ("Add a line to the Inputs box for each input() call, then
      press Trace again."). Without one the pane is left empty, never showing
      its "Press Run" placeholder after a failure.
    * ``input_key``: the panel input to fix. Its box is marked and scrolled
      into view until the teacher edits it or runs again.
    * ``input_hint``: a short line shown under that input, in place of its
      help, while it is marked ("Needs 2 lines: one per input() call.").
    """

    def __init__(
        self, message: str, *, next_step: str = "", input_key: str = "", input_hint: str = ""
    ) -> None:
        super().__init__(message)
        self.next_step = next_step
        self.input_key = input_key
        self.input_hint = input_hint


@dataclass
class RunResult:
    """What a run produced. Keys match the panel's output widgets.

    ``summary`` is the one line the CLI prints and the run log keeps.
    ``outcome`` is the shorter line the shell's result strip shows ("10
    questions · seed 42"): what was made, not where it went, because the strip
    shows the files as buttons beside it. Text before the first `` · `` is the
    headline. Empty: the strip shows ``summary``.

    ``labels`` optionally names a file's button (``{chart: "Chart"}``); a file
    without one is named from its file name (see :mod:`staffroom.core.outcome`).

    ``pages`` fills a ``PagePreview`` with the PDFs the run wrote (build the
    value with :func:`staffroom.core.panel.pages_from`). Paths only: the shell
    reads the files.
    """

    tables: dict[str, Table] = field(default_factory=dict)
    images: dict[str, Path] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)
    files: list[Path] = field(default_factory=list)
    summary: str = ""
    outcome: str = ""
    labels: dict[Path, str] = field(default_factory=dict)
    pages: dict[str, Pages] = field(default_factory=dict)


@dataclass
class RunContext:
    """Services the host gives a running tool. ``progress`` takes a fraction in
    [0, 1] and a short message; ``log`` sends a line to the run log. Call
    :meth:`warn` (not ``log``) for something the teacher should act on: it is
    logged as ``Warning: …`` and the shell counts it in the result strip."""

    config: Config
    output_dir: Path
    progress: Callable[[float, str], None] = lambda _f, _m: None
    log: Callable[[str], None] = lambda _m: None
    resources: ResourceService | None = None  # the Resource Library, when the host has one
    warned: Callable[[str], None] = lambda _m: None  # the host's hook; tools call warn()

    def warn(self, message: str) -> None:
        """Log ``Warning: <message>`` and tell the host there is one more warning."""
        self.log("Warning: " + message)
        self.warned(message)

    def note_run(self, tool: str) -> None:
        """Record that ``tool`` ran (for the usage review). Hosts call this;
        the shell does it in its worker, CLIs after a successful run."""
        from staffroom.core.usage import record_run

        record_run(tool)


DEFAULT_ORDER = 1000
"""Sidebar position for a plugin that declares no ``order``: after every tool
that does, alphabetically."""

GROUPS: tuple[str, ...] = ("Lessons", "Sheets & quizzes", "From a program", "After a test")
"""The sidebar's groups, in the order of a teacher's week: things for this
lesson, sheets and quizzes, things made from a program, after a test. A
plugin's ``group`` names one of these (or a group of its own, which the
sidebar shows after these, A-Z)."""

OTHER_GROUP = "Other"
"""Where a plugin that declares no ``group`` is listed: last."""


@runtime_checkable
class ToolPlugin(Protocol):
    """Required: ``name``, ``description``, ``version`` and the three methods.

    Optional class attributes the host also reads (all are read with
    ``getattr`` so a plugin without them needs no change):

    * ``order: int`` places the tool within its sidebar group, and so in the
      ``⌘1``-``⌘9`` shortcuts; lower comes first, ties break by name. Without
      it the tool sits after every ordered one (see :func:`plugin_order`).
    * ``hidden: bool`` keeps the tool out of the launcher sidebar and the
      number shortcuts. It still loads, still has its ``staff <name>`` commands,
      and ``staff list`` shows it with a marker. For reference and developer
      tools, not for anything a teacher should find.
    * ``group: str`` is the sidebar group the tool is listed under, one of
      :data:`GROUPS` (see :func:`plugin_group`). Without it the tool lands in
      :data:`OTHER_GROUP`, after every named group.
    * ``glyph: str`` names the tool's monochrome sidebar glyph, one of the
      shell's bundled glyphs (``shell/assets/glyphs/<name>.svg``). An unknown
      or missing name gets the shell's generic glyph. Plain data: the shell
      draws it, so a tool still never touches Qt.
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


def plugin_group(plugin: ToolPlugin) -> str:
    """The plugin's declared ``group``, or :data:`OTHER_GROUP`."""
    value = getattr(plugin, "group", None)
    return value.strip() if isinstance(value, str) and value.strip() else OTHER_GROUP


def plugin_glyph(plugin: ToolPlugin) -> str:
    """The plugin's declared ``glyph`` name, or ``""`` for the generic one."""
    value = getattr(plugin, "glyph", None)
    return value.strip() if isinstance(value, str) else ""
