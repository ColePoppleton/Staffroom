"""Declarative UI for hello. Only vocabulary from core.panel is used."""

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
from staffroom.tools.hello.logic import Options, question_columns


def output_folder(inputs: Mapping[str, Any], config: Config) -> Path:
    """Where a run writes: the output folder set in Settings, else
    ``<sessions root>/outputs/hello``. Never next to the input."""
    return config.output_dir_for(None, "hello")


def found(table: Table) -> list[Note]:
    """The lines under the file chip: what was read, what was dropped."""
    questions = question_columns(table.columns, Options().prefix)
    notes = [Note(f"{len(table)} scripts × {len(questions)} questions", ok=bool(questions))]
    if table.dropped_columns:
        notes.append(Note("Identifier columns dropped: " + ", ".join(table.dropped_columns)))
    return notes


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Hello",
        description="Reads a marks file (one row per script, q1..qn) and summarises each question.",
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
