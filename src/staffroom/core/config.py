"""User configuration: a TOML file at ``~/.config/staffroom/config.toml``.

``[general]`` holds shell-wide settings; ``[tools.<name>]`` holds a free-form
table per tool. Tools read their section through :meth:`Config.tool`.
"""

from __future__ import annotations

import errno
import logging
import tomllib
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from pathlib import Path
from typing import Any, Literal

import tomli_w

from staffroom.core import paths
from staffroom.core.atomic import atomic_write_text

log = logging.getLogger(__name__)

Theme = Literal["dark", "light"]

#: errno values that mean "this file or folder may not be written".
_READ_ONLY_ERRNOS = frozenset({errno.EACCES, errno.EPERM, errno.EROFS})


@dataclass(frozen=True)
class NotSaved:
    """Why ``config.toml`` was not written (#74). ``str()`` is the line for
    the teacher; ``reason`` reads after the path ("is read-only")."""

    path: Path
    reason: str

    @classmethod
    def from_error(cls, path: Path, exc: OSError) -> NotSaved:
        if exc.errno in _READ_ONLY_ERRNOS:
            return cls(path, "is read-only")
        return cls(path, f"cannot be written ({exc.strerror or exc})")

    def __str__(self) -> str:
        return (
            f"Settings could not be saved: {self.path} {self.reason}. Changes last until you quit."
        )


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
    # The released branch the installed app follows: `staff update` and the
    # Updates card compare HEAD with origin/<release_branch>, whatever branch
    # the checkout is on.
    release_branch: str = "main"
    # An installed copy asks GitHub for the newest release when it opens, at
    # most once a day (Settings > Updates, #11). *Check again* asks anyway.
    check_for_releases: bool = True
    # Folders and files under the resources root the library must not index or
    # list: names (any depth, * and ? allowed) or paths from the root.
    library_exclude: list[str] = field(default_factory=list)


@dataclass
class Config:
    general: GeneralSettings = field(default_factory=GeneralSettings)
    tools: dict[str, dict[str, Any]] = field(default_factory=dict)
    path: Path = field(default_factory=paths.config_file)
    read_only: bool = False  # set for one-off runs (screenshots) that must not persist
    # The day panels *show* (e.g. Classroom's "Copies to …/<day>"), pinned by
    # ``staffroom --screenshot --today`` so docs renders do not change daily.
    # Never loaded or saved, never where a run writes: None means today.
    screenshot_day: date | None = None
    # One log warning per session when saving fails, however many settings change.
    _save_warned: bool = field(default=False, init=False, repr=False, compare=False)

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

    def save(self) -> NotSaved | None:
        """Write ``config.toml``. Returns ``None`` when it was written (or the
        config is ``read_only``), else a :class:`NotSaved` the caller can show
        the teacher. Never raises ``OSError``: a config home that cannot be
        written (a locked-down school account, #74) keeps every change in
        memory for the session and logs one warning, not a traceback per click."""
        if self.read_only:
            return None
        payload: dict[str, Any] = {"general": asdict(self.general), "tools": self.tools}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # A temporary file then a rename (#125): a failed write leaves the
            # old config.toml whole instead of truncated.
            atomic_write_text(self.path, tomli_w.dumps(payload))
        except OSError as exc:
            failure = NotSaved.from_error(self.path, exc)
            if not self._save_warned:
                self._save_warned = True
                log.warning(
                    "Cannot save %s (%s); changes last for this session only",
                    self.path,
                    exc.strerror or exc,
                )
            return failure
        return None


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
