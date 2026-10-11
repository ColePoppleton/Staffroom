"""Declarative UI for classroom."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any

from staffroom.core import paths
from staffroom.core.config import Config
from staffroom.core.panel import (
    Action,
    ActionTable,
    LogArea,
    PanelSpec,
    ResourcePicker,
    TextField,
    TextView,
    WritesTo,
)
from staffroom.tools.classroom.logic import session_folder


def copies_to(inputs: Mapping[str, Any], config: Config, *, today: date | None = None) -> Path:
    """Where "Open for class" will put the copy: ``<sessions root>/<today>/<label>``,
    or just ``<sessions root>/<today>`` until the label is valid.

    A docs screenshot pins the day shown with ``config.screenshot_day`` (#116).
    That only changes this label: ``plugin.run`` ignores it and always copies
    into today's folder."""
    root = paths.sessions_root(config.general.sessions_root)
    day = today or config.screenshot_day or date.today()
    try:
        return root / session_folder(day, str(inputs.get("label") or ""))
    except ValueError:
        return root / day.isoformat()


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
                place="main",
            ),
            TextView(key="diff", label="Diff vs original", place="below"),
            LogArea(),
        ),
        run_label="Open for class",
        writes_to=WritesTo(copies_to, verb="Copies to", open_label="Open sessions folder"),
    )
