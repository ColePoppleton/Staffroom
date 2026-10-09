"""Which tools actually get used. PHASES.md asks for a review after a month;
this records the evidence: run counts and last-used dates per tool, in
``~/.config/staffroom/usage.toml``. Nothing about inputs is stored.

Both hosts record here. The launcher's worker does so after every ``run``;
``staff`` does so after every tool command that completes without a
``ToolError`` (see ``staffroom.cli``). ``runs`` is the total across both;
``cli_runs`` is the CLI's share, so launcher use is what remains. Files written
before the CLI counted (total only) need no migration: all of it was the
launcher's."""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import tomli_w

from staffroom.core import paths

log = logging.getLogger(__name__)

Source = Literal["launcher", "cli"]


@dataclass(frozen=True)
class ToolUsage:
    name: str
    runs: int  # launcher and CLI together
    last_used: str  # ISO date or ""
    cli_runs: int = 0

    @property
    def launcher_runs(self) -> int:
        return max(self.runs - self.cli_runs, 0)


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


def _count(entry: dict[str, object], key: str) -> int:
    return int(str(entry.get(key, 0) or 0))


def record_run(
    tool: str,
    *,
    path: Path | None = None,
    when: datetime | None = None,
    source: Source = "launcher",
) -> bool:
    """Count one run of ``tool`` from ``source``. Returns False, and logs, when
    the file cannot be written (a read-only home): a usage counter must never
    stop a tool from finishing its job."""
    path = path or usage_file()
    data = _load(path)
    entry = data.setdefault(tool, {"runs": 0, "last_used": ""})
    entry["runs"] = _count(entry, "runs") + 1
    if source == "cli":
        entry["cli_runs"] = _count(entry, "cli_runs") + 1
    entry["last_used"] = (when or datetime.now(UTC)).date().isoformat()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(tomli_w.dumps({"tools": data}), encoding="utf-8")
    except OSError as exc:
        log.debug("usage not recorded (%s): %s", path, exc)
        return False
    return True


def summary(path: Path | None = None) -> list[ToolUsage]:
    data = _load(path or usage_file())
    out = [
        ToolUsage(
            name,
            _count(v, "runs"),
            str(v.get("last_used", "") or ""),
            min(_count(v, "cli_runs"), _count(v, "runs")),
        )
        for name, v in data.items()
    ]
    return sorted(out, key=lambda u: (-u.runs, u.name))
