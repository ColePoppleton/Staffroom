"""Declarative UI for marks."""

from __future__ import annotations

from teaching_tools.core.config import load_config
from teaching_tools.core.panel import (
    Column,
    EditableTable,
    FilePicker,
    ImageView,
    LogArea,
    OptionsForm,
    PanelSpec,
    ResultsTable,
    TablePreview,
)
from teaching_tools.tools.marks.logic import Options
from teaching_tools.tools.marks.presets import all_presets, default_preset_for


def panel_spec() -> PanelSpec:
    config = load_config()
    presets = all_presets(config)
    default = default_preset_for(config.general.board)
    return PanelSpec(
        title="Marks",
        description=(
            "Raw marks per question, one row per script, no names: grades, distribution, "
            "and which questions to reteach. Only class-level results are ever saved."
        ),
        inputs=(
            FilePicker(
                key="marks",
                label="Marks file",
                help="CSV or XLSX with q1, q2, … columns. Identifier columns are dropped. "
                "A row flagged MAX gives the max per question.",
            ),
            TablePreview(key="preview", source="marks", label="Marks preview"),
            EditableTable(
                key="boundaries",
                label="Grade boundaries",
                help="Lowest mark for each grade, as % of the paper or raw marks (see options). "
                "Presets are starting points: edit them to the published boundaries.",
                columns=(Column("Grade", "text", 90), Column("Minimum", "float", 110)),
                rows=presets.get(default, next(iter(presets.values()))),
                presets=tuple(presets.items()),
                preset_action="save_preset",
            ),
            OptionsForm(key="options", schema=Options),
        ),
        outputs=(
            ResultsTable(key="distribution", label="Grade distribution"),
            ImageView(key="chart", label="Distribution chart"),
            ResultsTable(key="questions", label="Per-question analysis"),
            ResultsTable(key="worst", label="Worst questions (reteach these)"),
            ResultsTable(key="grades", label="Per-script grades (view only, never saved)"),
            LogArea(),
        ),
        run_label="Analyse",
    )
