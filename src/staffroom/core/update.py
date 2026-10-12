"""Self-update from the git remote: fetch, report how far behind the released
branch this checkout is, pull fast-forward, sync dependencies. Used by
``staff update``, the launcher's Settings page and its startup check.

The comparison is always against the *release* branch on the remote
(``origin/main`` unless ``release_branch`` is set in config), whatever branch
the checkout is on: the owner's copy may sit on ``dev`` or a feature branch
and should still learn that a release is out. A checkout on another branch,
with no upstream, or detached is described in one plain line and is never
pulled. Never force-pushes, never switches branch, never discards local
changes: a dirty tree or a diverged branch is reported, not fixed.

Only this project's own checkout is ever updated. Unless a test passes
``repo`` explicitly, :func:`status` and :func:`apply` first ask
:func:`staffroom.core.install.detect`; an installed copy (``uv tool
install``, a wheel, a bundle) gets one plain line on how to update it and
**no git command runs at all** (#9).

An installed copy learns about releases another way (#11):
:func:`check_latest_release` asks GitHub's public Releases API for the
newest release, over HTTPS with a short timeout, no token and nothing about
the teacher. The launcher asks when the teacher presses *Check again*, and at
start at most once a day while ``check_for_releases`` is on; the last answer
is kept in ``release-check.json`` beside ``config.toml`` so the card and the
sidebar footer can show it without asking again. It never runs git and never
installs anything: the card shows the one command to paste."""

from __future__ import annotations

import json
import re
import subprocess
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from staffroom.core import install, paths
from staffroom.core.atomic import atomic_write_text
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
    installed: str = ""  # an installed copy: how to update it; nothing was asked of git

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
        if self.installed:
            return self.installed
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
    ``fetch`` is False; never changes the working tree. With no ``repo``, an
    installed copy is answered without running git (:func:`installed_status`)."""
    if repo is None:
        here = install.detect()
        if not here.is_checkout or here.root is None:
            return installed_status(here)
        repo = here.root
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


def installed_status(here: install.Installation) -> UpdateStatus:
    """The status of an installed copy: never behind, nothing to apply, and
    the one line that says how to update it. Asks nothing of git."""
    return UpdateStatus(
        here.package_dir, "", "", "", 0, 0, False, on_release=False, installed=here.update_hint()
    )


def apply(repo: Path | None = None, *, sync: bool = True, release_branch: str | None = None) -> str:
    """Fast-forward the release branch to the remote and sync dependencies.
    Returns a one-line summary. Raises RuntimeError when the tree is dirty,
    the checkout is not on the release branch, the branch has diverged, or
    git fails, and (before any git runs) when this is an installed copy.
    Never switches branch."""
    if repo is None:
        here = install.detect()
        if not here.is_checkout or here.root is None:
            raise RuntimeError(here.update_hint())
        repo = here.root
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


# -- releases, for an installed copy (#11) ------------------------------------

#: The one address the release check asks. Public, read-only, no token.
RELEASES_API = "https://api.github.com/repos/ColePoppleton/Staffroom/releases/latest"
RELEASES_PAGE = "https://github.com/ColePoppleton/Staffroom/releases"
RELEASE_TIMEOUT = 5.0  # seconds; a slow school network gives up quickly
CHECK_EVERY = timedelta(days=1)  # the start check asks at most this often
MAX_RESPONSE = 1_000_000  # bytes read from the answer; a release is a few KB
RELEASE_CACHE = "release-check.json"
UNREACHABLE = "Could not reach GitHub, so Staffroom cannot tell whether a newer release is out."
UNREADABLE = (
    "GitHub's answer could not be read, so Staffroom cannot tell whether a newer release is out."
)

#: ``fetch(url, timeout) -> body``. The real one is :func:`https_get`; tests
#: pass a fake so no test touches the network.
Fetch = Callable[[str, float], bytes]


@dataclass(frozen=True)
class Release:
    version: str  # "0.9.0", from the tag "v0.9.0"
    url: str  # the release's page on GitHub
    published: str = ""  # ISO date, "2026-10-14"; "" when GitHub gave none
    notes: str = ""  # the release notes, Markdown


@dataclass(frozen=True)
class ReleaseCheck:
    """One answer from the release check: the newest release, or the plain
    sentence saying why there is none. Never "up to date" after a failure."""

    checked_at: datetime  # when it asked, UTC
    release: Release | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.release is not None and not self.error

    def newer_than(self, running: str) -> bool | None:
        """True when the newest release is ahead of ``running``, False when
        it is not, None when the check failed (nothing is claimed)."""
        if not self.ok or self.release is None:
            return None
        newest, here = version_key(self.release.version), version_key(running)
        if newest is None or here is None:
            return None
        return newest > here

    def to_json(self) -> dict[str, Any]:
        data: dict[str, Any] = {"checked_at": self.checked_at.isoformat()}
        if self.release is not None:
            data["release"] = {
                "version": self.release.version,
                "url": self.release.url,
                "published": self.release.published,
                "notes": self.release.notes,
            }
        if self.error:
            data["error"] = self.error
        return data

    @classmethod
    def from_json(cls, data: object) -> ReleaseCheck | None:
        if not isinstance(data, dict):
            return None
        try:
            checked = datetime.fromisoformat(str(data["checked_at"]))
        except (KeyError, ValueError):
            return None
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=UTC)
        raw = data.get("release")
        release = None
        if isinstance(raw, dict) and isinstance(raw.get("version"), str):
            release = Release(
                version=raw["version"],
                url=str(raw.get("url") or RELEASES_PAGE),
                published=str(raw.get("published") or ""),
                notes=str(raw.get("notes") or ""),
            )
        error = str(data.get("error") or "")
        if release is None and not error:
            return None
        return cls(checked, release, error)


def version_key(text: str) -> tuple[int, int, int] | None:
    """``"0.9.0"`` or ``"v0.9.0"`` as a comparable tuple; None for anything
    that is not a plain release number (a pre-release, a commit)."""
    m = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", text.strip())
    return (int(m[1]), int(m[2]), int(m[3])) if m else None


def https_get(url: str, timeout: float) -> bytes:
    """GET ``url`` (HTTPS only) and return the body. Sends GitHub's Accept
    header and a bare ``Staffroom`` user agent (GitHub requires one); no
    token, cookie or anything about the teacher."""
    if not url.startswith("https://"):
        raise ValueError(f"refusing a non-HTTPS URL: {url}")
    request = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Staffroom"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body: bytes = response.read(MAX_RESPONSE)
    return body


def check_latest_release(
    fetch: Fetch | None = None, *, now: datetime | None = None
) -> ReleaseCheck:
    """Ask GitHub for the newest published release. Never raises and never
    runs git: any failure is a :class:`ReleaseCheck` with one plain sentence."""
    when = now or datetime.now(UTC)
    try:
        body = (fetch or https_get)(RELEASES_API, RELEASE_TIMEOUT)
    except (OSError, ValueError, TimeoutError) as exc:  # URLError and HTTPError are OSErrors
        log.info("release check failed: %s", exc)
        return ReleaseCheck(when, error=UNREACHABLE)
    release = _parse_release(body)
    if release is None:
        log.info("release check: an answer without a release version")
        return ReleaseCheck(when, error=UNREADABLE)
    log.info("release check: newest release %s", release.version)
    return ReleaseCheck(when, release)


def _parse_release(body: bytes) -> Release | None:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name")
    if not isinstance(tag, str) or version_key(tag) is None:
        return None
    url = data.get("html_url")
    if not isinstance(url, str) or not url.startswith("https://github.com/"):
        url = f"{RELEASES_PAGE}/tag/{tag}"
    published = str(data.get("published_at") or "")[:10]
    return Release(tag.lstrip("v"), url, published, str(data.get("body") or ""))


def notes_for_display(markdown: str) -> str:
    """Release notes as the card shows them: the teacher summary and the
    update line only. The folded *For contributors* list (``<details>``, see
    ``scripts/release.py notes``) is left out; the card links to the release
    page for anyone who wants it. Images and HTML comments are dropped (the
    card never fetches anything, so a picture would be a broken box), and an
    empty body is said plainly."""
    text = re.sub(r"<!--.*?-->", "", markdown, flags=re.S)
    text = re.split(r"<details\b", text, maxsplit=1, flags=re.I)[0]
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"<img\b[^>]*>", "", text, flags=re.I)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text or "This release has no notes."


def release_cache_file() -> Path:
    return paths.home_dir() / RELEASE_CACHE


def load_release_check(path: Path | None = None) -> ReleaseCheck | None:
    """The last answer kept on disk, or None when there is none (or it is
    unreadable)."""
    try:
        data = json.loads((path or release_cache_file()).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return ReleaseCheck.from_json(data)


def save_release_check(check: ReleaseCheck, path: Path | None = None) -> bool:
    """Keep ``check`` for the next start. False when it could not be written
    (a read-only home); the answer still shows for this session."""
    target = path or release_cache_file()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, json.dumps(check.to_json(), indent=2) + "\n")
    except OSError as exc:
        log.warning("could not keep the release check in %s: %s", target, exc)
        return False
    return True


def release_check_due(last: ReleaseCheck | None, now: datetime | None = None) -> bool:
    """Whether the start check should ask again: never asked, or the last
    ask (successful or not) was at least :data:`CHECK_EVERY` ago. A clock
    that went backwards counts as due."""
    if last is None:
        return True
    elapsed = (now or datetime.now(UTC)) - last.checked_at
    return elapsed >= CHECK_EVERY or elapsed < timedelta(0)


def release_date_text(iso: str) -> str:
    """``"2026-10-14"`` as the card prints it, ``"14 Oct 2026"``; ``""`` when
    there is no usable date."""
    try:
        day = datetime.fromisoformat(iso[:10]).date()
    except ValueError:
        return ""
    return f"{day.day} {day:%b %Y}"


def age_text(then: datetime, now: datetime | None = None) -> str:
    """How long ago ``then`` was, in words: *just now*, *5 minutes ago*,
    *3 hours ago*, *yesterday*, *on 14 Oct 2026*."""
    seconds = ((now or datetime.now(UTC)) - then).total_seconds()
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    if hours < 48:
        return "yesterday"
    return f"on {release_date_text(then.date().isoformat())}"
