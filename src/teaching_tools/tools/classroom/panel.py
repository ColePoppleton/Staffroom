"""Declarative UI for classroom."""

from __future__ import annotations

from teaching_tools.core.panel import (
    Action,
    ActionTable,
    LogArea,
    PanelSpec,
    ResourcePicker,
    TextField,
    TextView,
)


def panel_spec() -> PanelSpec:
    return PanelSpec(
        title="Classroom",
        description=(
            "Open a resource for a lesson without touching the original: a copy goes into "
            "the sessions folder and opens in your editor."
        ),
        inputs=(
            ResourcePicker(
                key="resource",
                label="Resource",
                help="A file from the library (or anywhere). The original is never modified.",
            ),
            TextField(
                key="label",
                label="Lesson label",
                placeholder="e.g. P3 Y9 loops",
                help="One short line naming the lesson. Not a class, not pupils, no names.",
                max_length=60,
            ),
        ),
        outputs=(
            ActionTable(
                key="sessions",
                label="Past sessions",
                actions=(
                    Action("diff", "Diff vs original", "Show what changed in the lesson"),
                    Action("reopen", "Re-open", "Launch the editor on this copy again"),
                    Action(
                        "promote",
                        "Promote",
                        "Copy back next to the original as <name>_v2 (never overwrites)",
                        primary=True,
                    ),
                ),
                refresh_action="refresh",
                hidden_columns=("Original", "Session file"),
            ),
            TextView(key="diff", label="Diff vs original"),
            LogArea(),
        ),
        run_label="Open for class",
    )
