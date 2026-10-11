"""``staff new <tool>``: stamp out a new tool package from string templates.

Only the standard library is used. The generated tool is a working, tested
example that follows the hard rules from its first commit (#18): it reads a
marks file (no identifiers; ``core.csvio`` drops them), shows and saves one
row per question (an aggregate, never a row per script), writes into the
output folder rather than next to the input (which may be the tracked
``examples/`` folder), and passes ``ruff check`` and ``ruff format`` as
generated. ``tests/test_scaffold.py`` holds it to all of that.

The templates are :class:`string.Template` strings: ``$name``, ``$class_name``
and ``$title`` are substituted, so a literal dollar sign is written ``$$``.
Keep the lines that hold ``$name`` short, so a long tool name still fits in
100 columns.
"""

from __future__ import annotations

import keyword
import re
from pathlib import Path
from string import Template

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_tool_name(name: str) -> str:
    if not _NAME_RE.match(name) or keyword.iskeyword(name):
        msg = f"{name!r} is not a valid tool name: use lowercase letters, digits and underscores"
        raise ValueError(msg)
    return name


def class_name_for(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_")) + "Plugin"


def title_for(name: str) -> str:
    return name.replace("_", " ").capitalize()


def scaffold_tool(name: str, tools_dir: Path) -> list[Path]:
    """Create ``tools_dir/<name>/`` and return the files written."""
    validate_tool_name(name)
    target = tools_dir / name
    if target.exists():
        msg = f"{target} already exists"
        raise FileExistsError(msg)
    subs = {"name": name, "class_name": class_name_for(name), "title": title_for(name)}
    written: list[Path] = []
    for rel, template in TEMPLATES.items():
        path = target / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(Template(template).substitute(subs), encoding="utf-8")
        written.append(path)
    return written


TEMPLATES: dict[str, str] = {
    "__init__.py": '''"""$title tool. TODO: one line on what it is for.

As generated it reads a marks file (one row per script, q1..qn, no
identifiers) and saves one row per question: how many scripts have a mark,
the mean and the highest. Replace ``logic.summarise`` with the real work and
keep the two rules it follows (docs/adding-a-tool.md):

* Nothing per row is saved. A run writes an aggregate, a sheet, a key or a
  chart; never the input's rows with a column added.
* Files go to the output folder (``panel.output_folder``), never next to the
  input, which may sit in a shared or tracked folder such as ``examples/``.
"""

from __future__ import annotations

from typing import Any

from staffroom.core.csvio import read_table, write_table
from staffroom.core.panel import PanelSpec
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.tools.$name import logic
from staffroom.tools.$name.panel import output_folder, panel_spec


class $class_name:
    name = "$name"
    description = "TODO: one line describing what $name does."
    version = "0.1.0"
    # Optional (see docs/adding-a-tool.md, "Where it sits in the sidebar"):
    #   group = "From a program"  sidebar group (core.plugin.GROUPS); unset lists it under Other
    #   glyph = "code"            sidebar glyph (shell/assets/glyphs/<name>.svg); unset is generic
    #   order = 50     lower comes first in its group; unset puts it after the shipped ones
    #   hidden = True  keep it out of the launcher (reference and developer tools)

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.$name.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        source = inputs.get("source")
        if source is None:
            raise ToolError("Choose a marks file first.")
        options = inputs.get("options") or logic.Options()
        ctx.progress(0.1, f"Reading {source.name}")
        table = read_table(source)  # identifier columns are already gone
        if table.dropped_columns:
            ctx.log("Dropped identifier column(s): " + ", ".join(table.dropped_columns))

        ctx.progress(0.5, "Summarising")
        try:
            summary = logic.summarise(table, options)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc

        # Not ctx.output_dir: with nothing set in Settings that is the input's
        # own folder. A summary of a file goes to the output folder instead.
        folder = output_folder(inputs, ctx.config)
        out = write_table(summary, folder / f"{source.stem}_summary.csv")
        ctx.progress(1.0, "Done")
        return RunResult(
            tables={"questions": summary},
            files=[out],
            summary=f"Summarised {len(summary)} questions from {len(table)} scripts into {out}",
            outcome=f"{len(summary)} questions · {len(table)} scripts",
        )


plugin = $class_name()
''',
    "logic.py": '''"""Pure functions for $title. No file I/O, no typer, no Qt: tables in,
tables out, so everything here is trivially unit-testable.

What comes out is class-level: one row per question, never one per script,
so nothing a run saves can be traced back to a row of the input."""

from __future__ import annotations

from dataclasses import dataclass, field

from staffroom.core.table import Cell, Table


@dataclass
class Options:
    """Rendered as a form by the shell; passed to :func:`summarise`."""

    prefix: str = field(
        default="q", metadata={"label": "Question column prefix", "help": "e.g. q for q1, q2…"}
    )


def question_columns(columns: list[str], prefix: str) -> list[str]:
    """Columns named ``<prefix><digits>``, case-insensitive: ``q1``, ``Q12``."""
    p = prefix.lower()
    return [c for c in columns if c.lower().startswith(p) and c[len(p) :].isdigit()]


def summarise(table: Table, options: Options) -> Table:
    """TODO: replace with the real work. One row per question: how many
    scripts have a mark for it, the mean and the highest mark."""
    questions = question_columns(table.columns, options.prefix)
    if not questions:
        msg = f"No question columns starting with {options.prefix!r} in {table.columns}"
        raise ValueError(msg)
    rows: list[list[Cell]] = []
    for question in questions:
        marks = [
            m
            for m in table.column(question)
            if isinstance(m, int | float) and not isinstance(m, bool)
        ]
        mean = round(sum(marks) / len(marks), 1) if marks else None
        rows.append([question, len(marks), mean, max(marks, default=None)])
    return Table(["Question", "Answered", "Mean", "Highest"], rows, fake_data=table.fake_data)
''',
    "panel.py": '''"""Declarative UI for $title. Only vocabulary from core.panel is allowed."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from staffroom.core.config import Config
from staffroom.core.panel import (
    FilePicker,
    Note,
    OptionsForm,
    PanelSpec,
    ResultsTable,
    TablePreview,
    WritesTo,
)
from staffroom.core.table import Table
from staffroom.tools.$name.logic import Options, question_columns


def output_folder(inputs: Mapping[str, Any], config: Config) -> Path:
    """Where a run writes: the output folder set in Settings, else
    ``<sessions root>/outputs/<tool>``. Never next to the input."""
    return config.output_dir_for(None, "$name")


def found(table: Table) -> list[Note]:
    """The lines under the file chip: what was read, what was dropped."""
    questions = question_columns(table.columns, Options().prefix)
    notes = [Note(f"{len(table)} scripts × {len(questions)} questions", ok=bool(questions))]
    if table.dropped_columns:
        notes.append(Note("Identifier columns dropped: " + ", ".join(table.dropped_columns)))
    return notes


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="$title",
        description="TODO: one line describing what $name does.",
        inputs=(
            FilePicker(
                key="source",
                label="Marks file",
                help="CSV or XLSX with q1, q2, … columns, one row per script. "
                "Identifier columns are dropped.",
                chip=True,
            ),
            TablePreview(key="preview", source="source", summary=found, compact=True),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(ResultsTable(key="questions", label="Per question"),),
        run_label="Summarise",
        writes_to=WritesTo(output_folder),
    )
''',
    "cli.py": '''"""``staff $name ...`` commands. Thin: parse arguments, call the plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from staffroom.core.config import load_config
from staffroom.core.csvio import read_table
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.$name.logic import Options
from staffroom.tools.$name.panel import output_folder


def register(app: typer.Typer) -> None:
    @app.command()
    def run(
        source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
        out: Annotated[Path | None, typer.Option("--out", "-o", help="Output folder")] = None,
    ) -> None:
        """Summarise SOURCE per question into the output folder (or --out).

        Example: staff $name run examples/marks_10x.csv
        """
        from staffroom.tools.$name import plugin

        config = load_config()
        config.read_only = True  # --out is for this run only; never saved to Settings
        if out is not None:
            config.general.output_dir = str(out)
        ctx = RunContext(
            config=config,
            output_dir=output_folder({}, config),
            progress=lambda _f, msg: typer.echo(msg, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        try:
            result = plugin.run({"source": source, "options": Options()}, ctx)
        except ToolError as exc:
            typer.secho(str(exc), fg=typer.colors.RED, err=True)
            raise typer.Exit(1) from None
        typer.echo(result.summary)

    @app.command()
    def preview(source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
        """Print the first rows of SOURCE (on screen only; nothing is saved).

        Example: staff $name preview examples/marks_10x.csv
        """
        table = read_table(source)
        typer.echo(" | ".join(table.columns))
        for row in table.rows[:10]:
            typer.echo(" | ".join("" if c is None else str(c) for c in row))
''',
    "tests/__init__.py": "",
    "tests/test_logic.py": """import pytest

from staffroom.core.table import Table
from staffroom.tools.$name.logic import Options, summarise


def test_summarise_gives_one_row_per_question_not_per_script() -> None:
    table = Table(["q1", "q2"], [[3, 4], [1, None], [2, 0]])
    result = summarise(table, Options())
    assert result.columns == ["Question", "Answered", "Mean", "Highest"]
    assert result.rows == [["q1", 3, 2.0, 3], ["q2", 2, 2.0, 4]]


def test_summarise_needs_question_columns() -> None:
    with pytest.raises(ValueError, match="No question columns"):
        summarise(Table(["mark"], [[5]]), Options())
""",
    "tests/test_run.py": """from pathlib import Path

from staffroom.core.config import Config
from staffroom.core.csvio import read_csv, write_table
from staffroom.core.plugin import RunContext
from staffroom.core.table import Table
from staffroom.tools.$name import plugin
from staffroom.tools.$name.logic import Options


def test_run_saves_a_summary_in_the_output_folder(tmp_path: Path) -> None:
    marks = Table(["q1", "q2"], [[3, 4], [1, 2], [2, 0]], fake_data=True)
    source = write_table(marks, tmp_path / "class" / "marks.csv")
    config = Config(path=tmp_path / "config.toml")
    config.general.output_dir = str(tmp_path / "out")
    # The shell's ctx.output_dir is the input's folder when nothing is set.
    ctx = RunContext(config=config, output_dir=source.parent)

    result = plugin.run({"source": source, "options": Options()}, ctx)

    assert [p.parent for p in result.files] == [tmp_path / "out"]
    assert sorted(p.name for p in source.parent.iterdir()) == ["marks.csv"]
    saved = read_csv(result.files[0])
    assert len(saved) == 2  # one row per question, none per script
""",
}
