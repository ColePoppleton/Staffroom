"""Which tools actually get used. PHASES.md asks for a review after a month;
this records the evidence: run counts and last-used dates per tool, in
``~/.config/staffroom/usage.toml``. Nothing about inputs is stored."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import tomli_w

from staffroom.core import paths


@dataclass(frozen=True)
class ToolUsage:
    name: str
    runs: int
    last_used: str  # ISO date or ""


def usage_file() -> Path:
    return paths.home_dir() / "usage.toml"


def _load(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    tools = raw.get("tools", {})
    return {k: dict(v) for k, v in tools.items() if isinstance(v, dict)}


def record_run(tool: str, *, path: Path | None = None, when: datetime | None = None) -> None:
    path = path or usage_file()
    data = _load(path)
    entry = data.setdefault(tool, {"runs": 0, "last_used": ""})
    entry["runs"] = int(str(entry.get("runs", 0) or 0)) + 1
    entry["last_used"] = (when or datetime.now(UTC)).date().isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps({"tools": data}), encoding="utf-8")


def summary(path: Path | None = None) -> list[ToolUsage]:
    data = _load(path or usage_file())
    out = [
        ToolUsage(name, int(str(v.get("runs", 0) or 0)), str(v.get("last_used", "") or ""))
        for name, v in data.items()
    ]
    return sorted(out, key=lambda u: (-u.runs, u.name))
