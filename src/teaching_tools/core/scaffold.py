"""``tt new <tool>``: stamp out a new tool package from string templates.

Only the standard library is used. The generated tool is a working, tested
no-op that reads a table and echoes it, ready to be edited.
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
    "__init__.py": '''"""$title tool."""

from __future__ import annotations

from typing import Any

from teaching_tools.core.csvio import read_table, write_table
from teaching_tools.core.plugin import Inputs, RunContext, RunResult, ToolError
from teaching_tools.tools.$name import logic
from teaching_tools.tools.$name.panel import panel_spec


class $class_name:
    name = "$name"
    description = "TODO: one line describing what $name does."
    version = "0.1.0"

    def register_cli(self, app: Any) -> None:
        from teaching_tools.tools.$name.cli import register

        register(app)

    def panel_spec(self):  # noqa: ANN201 - type lives in core.panel
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        source = inputs.get("source")
        if source is None:
            raise ToolError("Choose an input file first.")
        ctx.progress(0.1, "Reading " + source.name)
        table = read_table(source)
        ctx.progress(0.5, "Processing")
        result = logic.process(table, inputs["options"])
        out = ctx.output_dir / (source.stem + "_$name" + source.suffix)
        write_table(result, out)
        ctx.progress(1.0, "Done")
        return RunResult(
            tables={"result": result},
            files=[out],
            summary="Wrote " + str(len(result)) + " rows to " + str(out),
        )


plugin = $class_name()
''',
    "logic.py": '''"""Pure functions for $title. No file I/O, no typer, no Qt: tables in,
tables out, so everything here is trivially unit-testable."""

from __future__ import annotations

from dataclasses import dataclass, field

from teaching_tools.core.table import Table


@dataclass
class Options:
    """Rendered as a form by the shell; passed to :func:`process`."""

    example_flag: bool = field(default=False, metadata={"label": "Example flag"})


def process(table: Table, options: Options) -> Table:
    """TODO: replace with the real transformation."""
    return table
''',
    "panel.py": '''"""Declarative UI for $title. Only vocabulary from core.panel is allowed."""

from __future__ import annotations

from teaching_tools.core.panel import (
    FilePicker,
    LogArea,
    OptionsForm,
    PanelSpec,
    ResultsTable,
    TablePreview,
)
from teaching_tools.tools.$name.logic import Options


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="$title",
        description="TODO: one line describing what $name does.",
        inputs=(
            FilePicker(key="source", label="Input file"),
            TablePreview(key="preview", source="source"),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(ResultsTable(key="result"), LogArea()),
        run_label="Run $name",
    )
''',
    "cli.py": '''"""``tt $name ...`` commands. Thin: parse arguments, call the plugin."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from teaching_tools.core.config import load_config
from teaching_tools.core.csvio import read_table
from teaching_tools.core.paths import default_output_dir
from teaching_tools.core.plugin import RunContext
from teaching_tools.tools.$name.logic import Options


def register(app: typer.Typer) -> None:
    @app.command()
    def run(
        source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)],
        out: Annotated[Path | None, typer.Option("--out", "-o", help="Output folder")] = None,
    ) -> None:
        """Process SOURCE and write the result next to it (or into --out)."""
        from teaching_tools.tools.$name import plugin

        config = load_config()
        ctx = RunContext(
            config=config,
            output_dir=out or default_output_dir(source, config.general.output_dir),
            progress=lambda _f, msg: typer.echo(msg, err=True),
            log=lambda msg: typer.echo(msg, err=True),
        )
        result = plugin.run({"source": source, "options": Options()}, ctx)
        typer.echo(result.summary)

    @app.command()
    def preview(source: Annotated[Path, typer.Argument(exists=True, dir_okay=False)]) -> None:
        """Print the first rows of SOURCE."""
        table = read_table(source)
        typer.echo(" | ".join(table.columns))
        for row in table.rows[:10]:
            typer.echo(" | ".join("" if c is None else str(c) for c in row))
''',
    "tests/__init__.py": "",
    "tests/test_logic.py": """from teaching_tools.core.table import Table
from teaching_tools.tools.$name.logic import Options, process


def test_process_returns_table() -> None:
    table = Table(["q1", "q2"], [[3, 4]])
    result = process(table, Options())
    assert result.columns[:2] == ["q1", "q2"]
    assert len(result) == 1
""",
}
