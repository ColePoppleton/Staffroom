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

PROJECT_NAME = "staffroom"
UV_RECEIPT = "uv-receipt.toml"  # uv writes this at the root of every tool environment
UV_UPGRADE_COMMAND = "uv tool upgrade staffroom"
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

    @property
    def is_checkout(self) -> bool:
        return self.kind is InstallKind.CHECKOUT

    @property
    def update_command(self) -> str:
        """The command that updates this copy, or ``""`` when there is no one
        command (a checkout updates itself; anything else is updated the way
        it was installed)."""
        return UV_UPGRADE_COMMAND if self.kind is InstallKind.UV_TOOL else ""

    def update_hint(self) -> str:
        """One plain line on how to update an installed copy; ``""`` for a
        checkout, which updates itself."""
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
        if any((env / UV_RECEIPT).is_file() for env in env_candidates):
            return Installation(InstallKind.UV_TOOL, here)
        return Installation(InstallKind.OTHER, here)
    root = here.parents[1] if here.parent.name == "src" else None
    if root is not None and _is_this_project(root) and (root / ".git").exists():
        return Installation(InstallKind.CHECKOUT, here, root)
    return Installation(InstallKind.OTHER, here)


def _is_this_project(root: Path) -> bool:
    try:
        with (root / "pyproject.toml").open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    project = data.get("project")
    return isinstance(project, dict) and project.get("name") == PROJECT_NAME
