"""How this copy of Staffroom is running: from its own git checkout, or as an
installed copy. The one place that decides it.

``staff update``, Settings > Updates and the startup check use it so an
installed copy never runs git (#9). The Updates card for installed copies
(#11) and the add-ons installer (#5) reuse it to pick the right command; do
not add a second test anywhere else.

Qt-free and cheap: a few ``stat`` calls and one small TOML read, no
subprocess. In particular it never runs ``git``: walking up from an installed
package and asking git would find whatever repository happens to enclose the
tool folder (a home folder kept as a dotfiles repository), which is the bug
this module exists to prevent.
"""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

PROJECT_NAME = "staffroom"
UV_RECEIPT = "uv-receipt.toml"  # uv writes this at the root of every tool environment
UV_UPGRADE_COMMAND = "uv tool upgrade staffroom"
DEFAULT_BRANCH = "main"
# The documented install line (#11): it follows ``main``, so the upgrade
# command above moves it to the newest release.
INSTALL_LINE = "uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@main"
_INSTALLED_DIRS = {"site-packages", "dist-packages"}


class InstallKind(StrEnum):
    CHECKOUT = "checkout"  # this project's own git work tree (the thin launcher, a clone)
    UV_TOOL = "uv-tool"  # ``uv tool install``, from git or a wheel
    OTHER = "other"  # pip into a venv, a PyInstaller bundle, an unpacked sdist


@dataclass(frozen=True)
class Installation:
    kind: InstallKind
    package_dir: Path  # the ``staffroom`` package folder that is running
    root: Path | None = None  # the checkout's root; None for an installed copy
    # A uv tool that ``uv tool upgrade`` can move: installed from the git
    # repository's ``main`` (or with no revision). False when uv's receipt
    # pins a tag (the install line before #11) or a wheel file: ``upgrade``
    # says "Nothing to upgrade" for those, so the install line is the command.
    tracks_main: bool = True

    @property
    def is_checkout(self) -> bool:
        return self.kind is InstallKind.CHECKOUT

    @property
    def update_command(self) -> str:
        """The command that updates this copy, or ``""`` when there is no one
        command (a checkout updates itself; anything else is updated the way
        it was installed). A uv tool pinned to a tag or a wheel gets the
        install line, which moves it onto ``main`` once; after that the
        upgrade command is enough."""
        if self.kind is not InstallKind.UV_TOOL:
            return ""
        return UV_UPGRADE_COMMAND if self.tracks_main else INSTALL_LINE

    def update_hint(self) -> str:
        """One plain line on how to update an installed copy; ``""`` for a
        checkout, which updates itself."""
        if self.kind is InstallKind.UV_TOOL and not self.tracks_main:
            return (
                "This copy was installed from a fixed release and never updates itself. "
                f"To update it, quit Staffroom and run: {INSTALL_LINE}"
            )
        if self.kind is InstallKind.UV_TOOL:
            return (
                "This copy was installed with uv and never updates itself. "
                f"To update it, quit Staffroom and run: {UV_UPGRADE_COMMAND}"
            )
        if self.kind is InstallKind.OTHER:
            return (
                "This copy was not installed from a git checkout and never updates "
                "itself. Update it the way it was installed."
            )
        return ""


def detect(package_dir: Path | None = None) -> Installation:
    """How the ``staffroom`` package at ``package_dir`` (default: the one
    running) is installed.

    It is a **checkout** only when all of these hold:

    1. the process is not a frozen bundle (PyInstaller);
    2. no folder above the package is ``site-packages`` / ``dist-packages``
       (an installed package lives there; an editable or ``uv run`` checkout
       imports straight from ``src/``);
    3. the package is ``<root>/src/staffroom`` and ``<root>/pyproject.toml``
       declares ``[project] name = "staffroom"``;
    4. ``<root>/.git`` exists (a folder, or the file a ``git worktree`` has),
       so ``<root>`` is the top level of its own work tree, not a folder
       inside some other repository.

    Otherwise it is an installed copy: ``UV_TOOL`` when the environment that
    holds the package has uv's ``uv-receipt.toml``, else ``OTHER``. Never runs
    git."""
    here = (package_dir or Path(__file__).resolve().parents[1]).resolve()
    if getattr(sys, "frozen", False):
        return Installation(InstallKind.OTHER, here)
    installed_in = next((p for p in here.parents if p.name in _INSTALLED_DIRS), None)
    if installed_in is not None:
        # <env>/lib/pythonX.Y/site-packages/staffroom; on Windows <env>/Lib/site-packages.
        env_candidates = (installed_in.parents[2], installed_in.parents[1])
        receipt = next(
            (env / UV_RECEIPT for env in env_candidates if (env / UV_RECEIPT).is_file()), None
        )
        if receipt is not None:
            return Installation(InstallKind.UV_TOOL, here, tracks_main=_tracks_main(receipt))
        return Installation(InstallKind.OTHER, here)
    root = here.parents[1] if here.parent.name == "src" else None
    if root is not None and _is_this_project(root) and (root / ".git").exists():
        return Installation(InstallKind.CHECKOUT, here, root)
    return Installation(InstallKind.OTHER, here)


def _tracks_main(receipt: Path) -> bool:
    """Whether uv's receipt says ``uv tool upgrade`` can move this tool: its
    ``staffroom`` requirement is a git URL on ``main`` or with no revision.
    A tag or commit (``?rev=v0.8.1``) or a local wheel (``path = …``) cannot
    move. An unreadable or unfamiliar receipt counts as movable, so the card
    shows the short command rather than guessing."""
    try:
        with receipt.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return True
    tool = data.get("tool")
    requirements = tool.get("requirements") if isinstance(tool, dict) else None
    if not isinstance(requirements, list):
        return True
    for req in requirements:
        if not isinstance(req, dict) or req.get("name") != PROJECT_NAME:
            continue
        if "path" in req:
            return False
        git = req.get("git")
        if isinstance(git, str):
            rev = parse_qs(urlsplit(git).query).get("rev", [""])[0]
            return rev in ("", DEFAULT_BRANCH)
    return True


def _is_this_project(root: Path) -> bool:
    try:
        with (root / "pyproject.toml").open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    project = data.get("project")
    return isinstance(project, dict) and project.get("name") == PROJECT_NAME
