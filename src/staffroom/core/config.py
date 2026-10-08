"""User configuration: a TOML file at ``~/.config/staffroom/config.toml``.

``[general]`` holds shell-wide settings; ``[tools.<name>]`` holds a free-form
table per tool. Tools read their section through :meth:`Config.tool`.
"""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Literal

import tomli_w

from staffroom.core import paths

Theme = Literal["dark", "light"]


@dataclass
class GeneralSettings:
    theme: Theme = "dark"
    output_dir: str = ""  # empty: next to the input, else <sessions_root>/outputs/<tool>
    log_level: str = "INFO"
    last_tool: str = ""
    resources_root: str = ""  # the teacher's resources folder; set in Settings
    sessions_root: str = ""  # empty means ~/TeachingSessions (local; never a cloud folder)
    editor_command: str = "open -a Thonny {file}"
    board: str = "ocr"  # default exam board for presets and tags: ocr | aqa
    house_header: str = ""  # e.g. the school or department name, shown before the title
    house_footer: str = ""  # e.g. "Computing Department", shown beside the page number
    show_hidden: bool = False
    sidebar_mode: str = "tools"


@dataclass
class Config:
    general: GeneralSettings = field(default_factory=GeneralSettings)
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    path: Path = field(default_factory=paths.config_file)
    read_only: bool = False  # set for one-off runs (screenshots) that must not persist

    def tool(self, name: str) -> dict[str, Any]:
        return self.tools.setdefault(name, {})

    def output_dir_for(self, input_path: Path | None, tool: str) -> Path:
        """Where ``tool`` should write for this input; see
        :func:`staffroom.core.paths.default_output_dir`."""
        return paths.default_output_dir(
            input_path,
            self.general.output_dir,
            resources_root=self.general.resources_root,
            sessions_root=self.general.sessions_root,
            tool=tool,
        )

    def save(self) -> Path:
        if self.read_only:
            return self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {"general": asdict(self.general), "tools": self.tools}
        with self.path.open("wb") as fh:
            tomli_w.dump(payload, fh)
        return self.path


def load_config(path: Path | None = None) -> Config:
    path = path or paths.config_file()
    if not path.exists():
        return Config(path=path)
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    general_raw = raw.get("general", {})
    known = {f.name for f in fields(GeneralSettings)}
    general = GeneralSettings(**{k: v for k, v in general_raw.items() if k in known})
    tools_raw = raw.get("tools", {})
    tools = {k: dict(v) for k, v in tools_raw.items() if isinstance(v, dict)}
    return Config(general=general, tools=tools, path=path)
