"""Self-update from the git remote: fetch, report how far behind the released
branch this checkout is, pull fast-forward, sync dependencies. Used by
``staff update``, the launcher's Settings page and its startup check.

The comparison is always against the *release* branch on the remote
(``origin/main`` unless ``release_branch`` is set in config), whatever branch
the checkout is on: the owner's copy may sit on ``dev`` or a feature branch
and should still learn that a release is out. A checkout on another branch,
with no upstream, or detached is described in one plain line and is never
pulled. Never force-pushes, never switches branch, never discards local
changes: a dirty tree or a diverged branch is reported, not fixed."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from staffroom.core import paths
from staffroom.core.log import get_logger

log = get_logger(__name__)
TIMEOUT = 30
DEFAULT_RELEASE_BRANCH = "main"


@dataclass(frozen=True)
class UpdateStatus:
    repo: Path
    commit: str  # short hash of HEAD
    branch: str  # local branch, or "HEAD" when detached
    remote: str  # the release ref compared against, e.g. "origin/main"; "" when no remote
    behind: int  # commits on the release ref that HEAD lacks
    ahead: int  # commits on HEAD that the release ref lacks
    dirty: bool
    error: str = ""
    on_release: bool = True  # HEAD is on the release branch itself
    upstream: str = ""  # the branch's own tracking ref, "" when it has none
    tag: str = ""  # newest vX.Y.Z tag on the release ref that HEAD lacks
    note: str = ""  # one plain line about the checkout: other branch, no upstream, detached
    head_tag: str = ""  # the vX.Y.Z tag HEAD sits on exactly, "" off a release tag

    @property
    def available(self) -> bool:
        """A release is ahead of this checkout, whatever branch it is on."""
        return self.behind > 0 and not self.error

    @property
    def can_apply(self) -> bool:
        """``apply`` would fast-forward: a release is ahead, the tree is clean,
        and the checkout is on the release branch and has not diverged."""
        return self.available and not self.dirty and self.on_release and not self.ahead

    def running_version(self, version: str) -> str:
        """The running version for people: ``0.6.0`` on a release tag,
        ``0.6.0 (dev, a1b2c3d)`` anywhere else, the bare version when git
        could not be read."""
        if self.error or self.head_tag or self.commit in ("", "?"):
            return version
        branch = "detached" if self.branch == "HEAD" else self.branch
        return f"{version} ({branch}, {self.commit})"

    def describe(self) -> str:
        if self.error:
            return f"Could not check: {self.error}"
        if not self.remote:
            return f"{self.commit} on {self.branch}; no remote configured"
        if self.behind == 0:
            line = f"Up to date with {self.remote} ({self.commit})"
        else:
            s = "s" if self.behind != 1 else ""
            latest = f", {self.tag}" if self.tag else ""
            line = f"{self.behind} update{s} available ({self.commit} → {self.remote}{latest})"
        return f"{line}; {self.note}" if self.note else line


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


def _try_git(args: Sequence[str], repo: Path) -> str:
    """Like :func:`_git`, but a command that fails because the thing asked
    about does not exist (no upstream, no tag, no such ref) yields "" instead
    of raising. Timeouts still propagate."""
    try:
        return _git(args, repo)
    except RuntimeError:
        return ""


def configured_release_branch() -> str:
    """The ``release_branch`` setting, ``main`` by default."""
    from staffroom.core.config import load_config

    try:
        return load_config().general.release_branch or DEFAULT_RELEASE_BRANCH
    except (OSError, ValueError):
        return DEFAULT_RELEASE_BRANCH


def _latest_tag_ahead(release: str, repo: Path) -> str:
    """The newest ``vX.Y.Z`` tag reachable from the release ref but not from HEAD."""
    tag = _try_git(["describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", release], repo)
    if not tag:
        return ""
    # merge-base prints nothing either way; exit 0 means HEAD already has the tag.
    already_here = (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", tag, "HEAD"],
            cwd=str(repo),
            capture_output=True,
            timeout=TIMEOUT,
            check=False,
        ).returncode
        == 0
    )
    return "" if already_here else tag


def status(
    repo: Path | None = None, *, fetch: bool = True, release_branch: str | None = None
) -> UpdateStatus:
    """Compare HEAD with the remote's release branch. Fetches first unless
    ``fetch`` is False; never changes the working tree."""
    repo = repo or paths.project_root()
    release_branch = release_branch or configured_release_branch()
    try:
        commit = _git(["rev-parse", "--short", "HEAD"], repo)
        branch = _git(["rev-parse", "--abbrev-ref", "HEAD"], repo)
        dirty = bool(_git(["status", "--porcelain", "--untracked-files=no"], repo))
        head_tag = _try_git(
            ["describe", "--tags", "--exact-match", "--match", "v[0-9]*", "HEAD"], repo
        )
        remotes = _git(["remote"], repo).split()
        if not remotes:
            return UpdateStatus(
                repo, commit, branch, "", 0, 0, dirty, on_release=False, head_tag=head_tag
            )
        remote_name = "origin" if "origin" in remotes else remotes[0]
        release = f"{remote_name}/{release_branch}"
        if fetch:
            _git(["fetch", "--quiet", remote_name], repo)
        if not _try_git(["rev-parse", "--verify", "--quiet", f"refs/remotes/{release}"], repo):
            raise RuntimeError(f"{remote_name} has no '{release_branch}' branch to update from")
        counts = _git(["rev-list", "--left-right", "--count", f"HEAD...{release}"], repo)
        ahead, behind = (int(x) for x in counts.split())
        upstream = _try_git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo)
        detached = branch == "HEAD"
        on_release = not detached and branch == release_branch
        if detached:
            note = f"detached (not on a branch); releases are on {release_branch}"
        elif not on_release:
            where = branch if upstream else f"{branch} (no upstream)"
            note = f"on {where}; releases are on {release_branch}"
        elif not upstream:
            note = f"{branch} has no upstream; comparing with {release}"
        else:
            note = ""
        tag = _latest_tag_ahead(release, repo) if behind else ""
        return UpdateStatus(
            repo,
            commit,
            branch,
            release,
            behind,
            ahead,
            dirty,
            on_release=on_release,
            upstream=upstream,
            tag=tag,
            note=note,
            head_tag=head_tag,
        )
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
            on_release=False,
        )


def apply(repo: Path | None = None, *, sync: bool = True, release_branch: str | None = None) -> str:
    """Fast-forward the release branch to the remote and sync dependencies.
    Returns a one-line summary. Raises RuntimeError when the tree is dirty,
    the checkout is not on the release branch, the branch has diverged, or
    git fails. Never switches branch."""
    repo = repo or paths.project_root()
    st = status(repo, release_branch=release_branch)
    if st.error:
        raise RuntimeError(st.error)
    if not st.remote:
        raise RuntimeError("No git remote to update from.")
    if st.dirty:
        raise RuntimeError("Local changes would be overwritten; commit or stash them first.")
    if not st.on_release:
        release = st.remote.partition("/")[2]
        raise RuntimeError(
            f"Not updated: this copy is {st.note}. "
            f"Switch to {release} first; updating never changes branch."
        )
    if st.ahead and st.behind:
        raise RuntimeError("This copy has diverged from the remote; merge by hand.")
    if not st.behind:
        return st.describe()
    _git(["merge", "--ff-only", st.remote], repo)
    if sync:
        uv = _find_uv()
        if uv:
            subprocess.run([uv, "sync", "--quiet"], cwd=str(repo), check=True, timeout=600)
    after = status(repo, fetch=False, release_branch=release_branch)
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
