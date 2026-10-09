"""Self-update against a local bare 'remote', no network. The release branch
is ``main``; the checkout may sit anywhere."""

import subprocess
from pathlib import Path

import pytest

from staffroom.core import update
from staffroom.core.config import Config


def git(*args: str, cwd: Path) -> str:
    env = {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(cwd),
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@x",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@x",
    }
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True, env=env
    ).stdout.strip()


@pytest.fixture
def repos(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    git("init", "--bare", "-q", "-b", "main", str(origin), cwd=tmp_path)
    upstream = tmp_path / "upstream"
    git("clone", "-q", str(origin), str(upstream), cwd=tmp_path)
    (upstream / "a.txt").write_text("1\n")
    git("add", "a.txt", cwd=upstream)
    git("commit", "-q", "-m", "one", cwd=upstream)
    git("push", "-q", "-u", "origin", "main", cwd=upstream)
    local = tmp_path / "local"
    git("clone", "-q", str(origin), str(local), cwd=tmp_path)
    return upstream, local


def release(upstream: Path, text: str, tag: str | None = None) -> None:
    """Push one more commit to main, optionally tagged."""
    (upstream / "a.txt").write_text(text)
    git("commit", "-q", "-am", text.strip(), cwd=upstream)
    if tag:
        git("tag", tag, cwd=upstream)
    git("push", "-q", "--tags", "origin", "main", cwd=upstream)


def test_status_and_apply_fast_forward(repos: tuple[Path, Path]) -> None:
    upstream, local = repos
    st = update.status(local)
    assert st.behind == 0 and st.remote == "origin/main" and st.describe().startswith("Up to date")
    assert st.on_release and st.upstream == "origin/main" and st.note == "" and st.tag == ""
    release(upstream, "2\n")
    st = update.status(local)
    assert st.behind == 1 and st.available and st.can_apply
    assert st.describe() == f"1 update available ({st.commit} → origin/main)"
    message = update.apply(local, sync=False)
    assert message.startswith("Updated") and (local / "a.txt").read_text() == "2\n"
    assert update.status(local).behind == 0


def test_release_tag_is_shown_when_ahead(repos: tuple[Path, Path]) -> None:
    upstream, local = repos
    release(upstream, "2\n", tag="v0.5.0")
    release(upstream, "3\n")
    st = update.status(local)
    assert st.tag == "v0.5.0" and st.behind == 2
    assert "2 updates available" in st.describe() and "v0.5.0" in st.describe()
    update.apply(local, sync=False)
    assert update.status(local).tag == ""  # nothing newer than what we have


def test_apply_refuses_dirty_or_diverged(repos: tuple[Path, Path]) -> None:
    upstream, local = repos
    release(upstream, "2\n")
    (local / "a.txt").write_text("local edit\n")
    assert not update.status(local).can_apply
    with pytest.raises(RuntimeError, match="Local changes"):
        update.apply(local, sync=False)
    git("checkout", "-q", "--", "a.txt", cwd=local)
    (local / "b.txt").write_text("x\n")
    git("add", "b.txt", cwd=local)
    git("commit", "-q", "-m", "local", cwd=local)
    st = update.status(local)
    assert st.ahead == 1 and st.behind == 1 and not st.can_apply
    with pytest.raises(RuntimeError, match="diverged"):
        update.apply(local, sync=False)


def test_main_without_upstream_still_compares_with_origin_main(
    repos: tuple[Path, Path],
) -> None:
    upstream, local = repos
    git("branch", "--unset-upstream", cwd=local)
    st = update.status(local)
    assert not st.error and st.remote == "origin/main" and st.upstream == ""
    assert st.note == "main has no upstream; comparing with origin/main"
    assert st.describe().startswith("Up to date with origin/main")
    release(upstream, "2\n")
    st = update.status(local)
    assert st.behind == 1 and st.can_apply
    assert update.apply(local, sync=False).startswith("Updated")


def test_other_branch_reports_against_release_and_never_pulls(
    repos: tuple[Path, Path],
) -> None:
    upstream, local = repos
    git("checkout", "-q", "-b", "dev", cwd=local)
    st = update.status(local)
    assert st.branch == "dev" and st.remote == "origin/main" and not st.on_release
    assert st.note == "on dev (no upstream); releases are on main"
    assert st.describe() == f"Up to date with origin/main ({st.commit}); {st.note}"
    git("push", "-q", "-u", "origin", "dev", cwd=local)
    release(upstream, "2\n", tag="v0.5.0")
    st = update.status(local)
    assert st.available and not st.can_apply and st.upstream == "origin/dev"
    assert st.describe() == (
        f"1 update available ({st.commit} → origin/main, v0.5.0); on dev; releases are on main"
    )
    with pytest.raises(RuntimeError, match="on dev; releases are on main"):
        update.apply(local, sync=False)
    assert git("rev-parse", "--abbrev-ref", "HEAD", cwd=local) == "dev"
    assert (local / "a.txt").read_text() == "1\n"


def test_detached_head(repos: tuple[Path, Path]) -> None:
    upstream, local = repos
    git("checkout", "-q", "--detach", cwd=local)
    release(upstream, "2\n")
    st = update.status(local)
    assert not st.error and st.behind == 1 and not st.on_release
    assert st.note == "detached (not on a branch); releases are on main"
    with pytest.raises(RuntimeError, match="detached"):
        update.apply(local, sync=False)


def test_release_branch_is_configurable(repos: tuple[Path, Path]) -> None:
    upstream, local = repos
    st = update.status(local, release_branch="stable")
    assert st.error == "origin has no 'stable' branch to update from"
    assert st.describe().startswith("Could not check")
    with pytest.raises(RuntimeError, match="no 'stable' branch"):
        update.apply(local, sync=False, release_branch="stable")
    git("push", "-q", "origin", "main:stable", cwd=upstream)
    config = Config()
    config.general.release_branch = "stable"
    config.save()  # the isolated STAFFROOM_HOME from conftest
    assert update.configured_release_branch() == "stable"
    st = update.status(local)
    assert st.remote == "origin/stable" and st.note == "on main; releases are on stable"


def test_no_remote_and_errors(tmp_path: Path) -> None:
    lone = tmp_path / "lone"
    lone.mkdir()
    git("init", "-q", "-b", "main", cwd=lone)
    (lone / "f").write_text("x")
    git("add", "f", cwd=lone)
    git("commit", "-q", "-m", "init", cwd=lone)
    st = update.status(lone)
    assert st.remote == "" and not st.available and "no remote" in st.describe()
    with pytest.raises(RuntimeError, match="No git remote"):
        update.apply(lone, sync=False)
    broken = update.status(tmp_path / "not-a-repo")
    assert broken.error and broken.describe().startswith("Could not check")
