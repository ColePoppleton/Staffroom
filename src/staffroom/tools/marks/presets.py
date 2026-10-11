"""Grade-boundary presets: built-in starting points plus any the teacher
saved, kept in ``config.tool("marks")["presets"]``."""

from __future__ import annotations

from staffroom.core.config import Config
from staffroom.core.panel import PresetRows
from staffroom.core.plugin import ToolError
from staffroom.core.table import Table

#: Percent-of-paper minimums. Illustrative: real boundaries change every
#: series, so edit them to the published ones for the paper in hand.
BUILTIN_PRESETS: dict[str, PresetRows] = {
    "OCR J277 (GCSE 9-1)": (
        ("9", 80),
        ("8", 72),
        ("7", 64),
        ("6", 56),
        ("5", 48),
        ("4", 40),
        ("3", 30),
        ("2", 20),
        ("1", 10),
        ("U", 0),
    ),
    "AQA 8525 (GCSE 9-1)": (
        ("9", 78),
        ("8", 70),
        ("7", 62),
        ("6", 54),
        ("5", 46),
        ("4", 38),
        ("3", 28),
        ("2", 18),
        ("1", 8),
        ("U", 0),
    ),
    "A-level (A*-E)": (
        ("A*", 80),
        ("A", 70),
        ("B", 60),
        ("C", 50),
        ("D", 40),
        ("E", 30),
        ("U", 0),
    ),
}

DEFAULT_PRESET = "OCR J277 (GCSE 9-1)"
BOARD_PRESETS = {"ocr": "OCR J277 (GCSE 9-1)", "aqa": "AQA 8525 (GCSE 9-1)"}


def default_preset_for(board: str) -> str:
    return BOARD_PRESETS.get(board.lower(), DEFAULT_PRESET)


def saved_presets(config: Config) -> dict[str, PresetRows]:
    raw = config.tool("marks").get("presets", {})
    out: dict[str, PresetRows] = {}
    if isinstance(raw, dict):
        for name, rows in raw.items():
            if isinstance(rows, list):
                out[str(name)] = tuple(
                    (str(r[0]), float(r[1])) for r in rows if isinstance(r, list) and len(r) >= 2
                )
    return out


def all_presets(config: Config) -> dict[str, PresetRows]:
    return {**BUILTIN_PRESETS, **saved_presets(config)}


def save_preset(config: Config, name: str, table: Table) -> None:
    """Keep ``name`` in the config and write it. The preset is in memory (and
    in the panel's list) whether or not the write works; when it does not,
    the teacher gets a ``ToolError`` saying so rather than a traceback (#74)."""
    rows = [[str(r[0]), float(r[1] or 0)] for r in table.rows if r and r[0] is not None]
    presets = config.tool("marks").setdefault("presets", {})
    presets[name] = rows
    problem = config.save()
    if problem is not None:
        raise ToolError(
            f"Preset {name!r} could not be saved: {problem.path} {problem.reason}. "
            "You can use it until you quit."
        )


def preset_table(rows: PresetRows) -> Table:
    return Table(["Grade", "Minimum"], [list(r) for r in rows])
