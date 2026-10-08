"""Self-update from the git remote: fetch, report how far behind, pull
fast-forward, sync dependencies. Used by ``staff update``, the launcher's
Settings page and its startup check. Never force-pushes, never discards
local changes: a dirty tree or a diverged branch is reported, not fixed."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from staffroom.core import paths
from staffroom.core.log import get_logger

log = get_logger(__name__)
TIMEOUT = 30


@dataclass(frozen=True)
class UpdateStatus:
    repo: Path
    commit: str  # short hash of HEAD
    branch: str
    remote: str  # "" when no remote
    behind: int
    ahead: int
    dirty: bool
    error: str = ""

    @property
    def available(self) -> bool:
        return self.behind > 0 and not self.error

    def describe(self) -> str:
        if self.error:
            return f"Could not check: {self.error}"
        if not self.remote:
            return f"{self.commit} on {self.branch}; no remote configured"
        if self.behind == 0:
            return f"Up to date ({self.commit} on {self.branch})"
        s = "s" if self.behind != 1 else ""
        return f"{self.behind} update{s} available ({self.commit} → {self.remote})"


def _git(args: Sequence[str], repo: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        env={
            "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
            "GIT_TERMINAL_PROMPT": "0",
            "HOME": str(Path.home()),
        },
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git {args[0]} failed")
    return result.stdout.strip()


def status(repo: Path | None = None, *, fetch: bool = True) -> UpdateStatus:
    repo = repo or paths.project_root()
    try:
        commit = _git(["rev-parse", "--short", "HEAD"], repo)
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
        dirty = bool(_git(["status", "--porcelain", "--untracked-files=no"], repo))
        remotes = _git(["remote"], repo).split()
        if not remotes:
            return UpdateStatus(repo, commit, branch, "", 0, 0, dirty)
        upstream = f"{remotes[0]}/{branch}"
        if fetch:
            _git(["fetch", "--quiet", remotes[0]], repo)
        counts = _git(["rev-list", "--left-right", "--count", f"HEAD...{upstream}"], repo)
        ahead, behind = (int(x) for x in counts.split())
        return UpdateStatus(repo, commit, branch, upstream, behind, ahead, dirty)
    except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
        return UpdateStatus(
            repo,
            "?",
            "?",
            "",
            0,
            0,
            False,
            error=str(exc).splitlines()[0] if str(exc) else "git error",
        )


def apply(repo: Path | None = None, *, sync: bool = True) -> str:
    """Fast-forward to the remote and sync dependencies. Returns a one-line
    summary. Raises RuntimeError when the tree is dirty, the branch has
    diverged, or git fails."""
    repo = repo or paths.project_root()
    st = status(repo)
    if st.error:
        raise RuntimeError(st.error)
    if st.dirty:
        raise RuntimeError("Local changes would be overwritten; commit or stash them first.")
    if not st.remote:
        raise RuntimeError("No git remote to update from.")
    if st.ahead and st.behind:
        raise RuntimeError("This copy has diverged from the remote; merge by hand.")
    if not st.behind:
        return st.describe()
    _git(["merge", "--ff-only", st.remote], repo)
    if sync:
        uv = _find_uv()
        if uv:
            subprocess.run([uv, "sync", "--quiet"], cwd=str(repo), check=True, timeout=600)
    after = status(repo, fetch=False)
    log.info("updated %s -> %s", st.commit, after.commit)
    plural = "s" if st.behind != 1 else ""
    return f"Updated {st.commit} → {after.commit} ({st.behind} commit{plural}). Restart to use it."


def _find_uv() -> str | None:
    for candidate in (
        Path.home() / ".local" / "bin" / "uv",
        Path("/opt/homebrew/bin/uv"),
        Path("/usr/local/bin/uv"),
    ):
        if candidate.exists():
            return str(candidate)
    return None
