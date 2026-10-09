"""Declarative UI for marks: a report, not a stack of tables (#87).

Inputs: the marks file as a chip with what was found in it (scripts by
questions, the MAX row, identifier columns dropped), the grade boundaries as
a compact grid with the preset and a % / raw switch, and the two options that
remain. Output: four headline tiles, the grade chart beside one per-question
table (hardest first, reteach marked), and the per-script grades folded away:
on screen only, never saved."""

from __future__ import annotations

from staffroom.core.config import load_config
from staffroom.core.panel import (
    BarChart,
    BarColumn,
    Choice,
    Column,
    EditableTable,
    FilePicker,
    LogArea,
    Note,
    OptionsForm,
    PanelSpec,
    ResultsTable,
    StatTiles,
    TablePreview,
)
from staffroom.core.table import Table
from staffroom.tools.marks.logic import INCOMPLETE_LABEL, MAX_FLAG, Options, load_summary
from staffroom.tools.marks.presets import all_presets, default_preset_for

GRADES_LABEL = "Per-script grades (view only, never saved)"
UNIT_CHOICE = Choice(
    key="unit",
    label="Boundaries in",
    choices=(("percent", "% of paper"), ("raw", "raw marks")),
    help="Read the minimums as a percentage of the paper or as raw marks",
)


def summary_notes(table: Table) -> list[Note]:
    return [Note(text, ok) for ok, text in load_summary(table)]


def panel_spec() -> PanelSpec:
    config = load_config()
    presets = all_presets(config)
    default = default_preset_for(config.general.board)
    return PanelSpec(
        title="Marks",
        description=(
            "Raw marks, no names: grades and which questions to reteach. "
            "Only class-level results are saved."
        ),
        inputs=(
            FilePicker(
                key="marks",
                label="Marks file",
                help="CSV or XLSX with q1, q2, … columns, one row per script. Identifier "
                "columns are dropped. A row flagged MAX gives the max per question.",
                chip=True,
            ),
            TablePreview(
                key="preview",
                source="marks",
                label="Marks file rows",
                flag=MAX_FLAG,
                summary=summary_notes,
                compact=True,
            ),
            EditableTable(
                key="boundaries",
                label="Grade boundaries",
                help="Click a number to edit it. Presets are a start: use the published "
                "boundaries for the paper in hand.",
                columns=(Column("Grade", "text", 90), Column("Minimum", "float", 110)),
                rows=presets.get(default, next(iter(presets.values()))),
                presets=tuple(presets.items()),
                preset_action="save_preset",
                compact=True,
                choice=UNIT_CHOICE,
            ),
            OptionsForm(key="options", schema=Options, fields=("max_marks", "worst_n")),
        ),
        outputs=(
            StatTiles(key="headline", label="Headline"),
            BarChart(
                key="distribution",
                label="Grades",
                category="Grade",
                value="Count",
                detail="Percent",
                detail_format="{:.0f}%",  # whole numbers under the bars; Table has the 1 dp
                skip=(INCOMPLETE_LABEL,),
            ),
            ResultsTable(
                key="questions",
                label="Questions, hardest first",
                bars=(BarColumn("Facility", 1.0),),
                tag_column="Reteach",
                hidden_columns=("Note",),
            ),
            ResultsTable(key="grades", label=GRADES_LABEL, place="below", collapsed=True),
            LogArea(),
        ),
        run_label="Analyse",
        main_layout="row",
    )
