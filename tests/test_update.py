"""Self-update against a local bare 'remote', no network."""

import subprocess
from pathlib import Path

import pytest

from staffroom.core import update


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


def test_status_and_apply_fast_forward(repos: tuple[Path, Path]) -> None:
    upstream, local = repos
    st = update.status(local)
    assert st.behind == 0 and st.remote == "origin/main" and st.describe().startswith("Up to date")
    (upstream / "a.txt").write_text("2\n")
    git("commit", "-q", "-am", "two", cwd=upstream)
    git("push", "-q", cwd=upstream)
    st = update.status(local)
    assert st.behind == 1 and st.available and "1 update available" in st.describe()
    message = update.apply(local, sync=False)
    assert message.startswith("Updated") and (local / "a.txt").read_text() == "2\n"
    assert update.status(local).behind == 0


def test_apply_refuses_dirty_or_diverged(repos: tuple[Path, Path]) -> None:
    upstream, local = repos
    (upstream / "a.txt").write_text("2\n")
    git("commit", "-q", "-am", "two", cwd=upstream)
    git("push", "-q", cwd=upstream)
    (local / "a.txt").write_text("local edit\n")
    with pytest.raises(RuntimeError, match="Local changes"):
        update.apply(local, sync=False)
    git("checkout", "-q", "--", "a.txt", cwd=local)
    (local / "b.txt").write_text("x\n")
    git("add", "b.txt", cwd=local)
    git("commit", "-q", "-m", "local", cwd=local)
    with pytest.raises(RuntimeError, match="diverged"):
        update.apply(local, sync=False)


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
