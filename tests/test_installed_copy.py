"""An installed copy never runs git (#9).

``core.install.detect`` is the one place that decides whether Staffroom runs
from this project's own checkout. Everything here builds its layouts under
``tmp_path``: the "home folder kept as a git repository", the uv tool folder
inside it, a pip venv, a clone. Nothing touches the real home or checkout,
apart from asking how the running test copy is installed.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import staffroom
from staffroom import __version__
from staffroom.cli import app
from staffroom.core import install, update
from staffroom.core.install import Installation, InstallKind

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(staffroom.__file__).resolve().parent
GIT_ENV = {
    "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@x",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@x",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def git(*args: str, cwd: Path) -> str:
    env = {**GIT_ENV, "HOME": str(cwd)}
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True, env=env
    ).stdout.strip()


def unrelated_repo(tmp_path: Path) -> Path:
    """A home folder kept as a git repository, with a remote that is one
    commit ahead: exactly what the old code fetched and fast-forwarded."""
    remote = tmp_path / "dotfiles.git"
    git("init", "--bare", "-q", "-b", "main", str(remote), cwd=tmp_path)
    home = tmp_path / "home"
    git("clone", "-q", str(remote), str(home), cwd=tmp_path)
    (home / ".zshrc").write_text("# one\n")
    git("add", ".zshrc", cwd=home)
    git("commit", "-q", "-m", "one", cwd=home)
    git("push", "-q", "-u", "origin", "main", cwd=home)
    other = tmp_path / "laptop"
    git("clone", "-q", str(remote), str(other), cwd=tmp_path)
    (other / ".zshrc").write_text("# two\n")
    git("commit", "-q", "-am", "two", cwd=other)
    git("push", "-q", "origin", "main", cwd=other)
    return home


def snapshot(repo: Path) -> dict[str, str]:
    """Every file under ``.git`` (HEAD, refs, reflog, FETCH_HEAD, objects…)
    by content hash: any git command that writes leaves a different map."""
    git_dir = repo / ".git"
    return {
        str(p.relative_to(git_dir)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(git_dir.rglob("*"))
        if p.is_file()
    }


def uv_tool_package(tool_dir: Path, *, package: Path | None = None) -> Path:
    """The layout ``uv tool install`` makes: ``<tool_dir>/staffroom`` is the
    environment, with uv's receipt and the package in site-packages."""
    env = tool_dir / "staffroom"
    site = env / "lib" / "python3.12" / "site-packages"
    site.mkdir(parents=True)
    (env / "uv-receipt.toml").write_text('[tool]\nrequirements = [{ name = "staffroom" }]\n')
    target = site / "staffroom"
    if package is None:
        target.mkdir()
        (target / "__init__.py").write_text("")
    else:
        shutil.copytree(package, target, ignore=shutil.ignore_patterns("__pycache__", "tests"))
    return target


def checkout(root: Path, *, name: str = "staffroom", git_dir: bool = True) -> Path:
    package = root / "src" / "staffroom"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (root / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.0.0"\n')
    if git_dir:
        (root / ".git").mkdir()
    return package


# -- detection -----------------------------------------------------------


def test_the_running_test_copy_is_this_checkout() -> None:
    """The owner's launcher and ``uv run`` import from ``src/``: a checkout,
    whose root is this repository."""
    here = install.detect()
    assert here.kind is InstallKind.CHECKOUT
    assert here.root == REPO_ROOT
    assert here.update_hint() == "" and here.update_command == ""


def test_a_clone_and_a_worktree_are_checkouts(tmp_path: Path) -> None:
    clone = checkout(tmp_path / "clone")
    assert install.detect(clone) == Installation(
        InstallKind.CHECKOUT, clone, (tmp_path / "clone").resolve()
    )
    worktree = checkout(tmp_path / "wt", git_dir=False)
    (tmp_path / "wt" / ".git").write_text("gitdir: /somewhere/.git/worktrees/wt\n")
    assert install.detect(worktree).is_checkout


def test_uv_tool_inside_an_unrelated_repository_is_installed(tmp_path: Path) -> None:
    home = unrelated_repo(tmp_path)
    package = uv_tool_package(home / ".local" / "share" / "uv" / "tools")
    here = install.detect(package)
    assert here.kind is InstallKind.UV_TOOL
    assert here.root is None
    assert here.update_command == "uv tool upgrade staffroom"
    assert "uv tool upgrade staffroom" in here.update_hint()


def test_uv_tool_outside_any_repository_is_installed(tmp_path: Path) -> None:
    package = uv_tool_package(tmp_path / "tools")
    assert install.detect(package).kind is InstallKind.UV_TOOL


GH = "https://github.com/ColePoppleton/Staffroom"


@pytest.mark.parametrize(
    ("requirement", "tracks_main"),
    [
        (f'{{ name = "staffroom", git = "{GH}?rev=main" }}', True),  # the line since #11
        (f'{{ name = "staffroom", git = "{GH}" }}', True),  # no revision: the default branch
        ('{ name = "staffroom" }', True),  # unfamiliar: show the short command
        (f'{{ name = "staffroom", git = "{GH}?rev=v0.8.1" }}', False),  # the line before #11
        ('{ name = "staffroom", path = "/Users/x/staffroom-0.8.1-py3-none-any.whl" }', False),
    ],
)
def test_the_update_command_follows_how_uv_installed_it(
    tmp_path: Path, requirement: str, tracks_main: bool
) -> None:
    """``uv tool upgrade`` only moves a tool installed from ``main``; uv
    answers *Nothing to upgrade* for a tag or a wheel. Read from the receipt
    uv writes (``[tool] requirements``), never from git."""
    package = uv_tool_package(tmp_path / "tools")
    (tmp_path / "tools" / "staffroom" / "uv-receipt.toml").write_text(
        f"[tool]\nrequirements = [{requirement}]\n"
    )
    here = install.detect(package)
    assert here.kind is InstallKind.UV_TOOL and here.tracks_main is tracks_main
    if tracks_main:
        assert here.update_command == "uv tool upgrade staffroom"
    else:
        assert here.update_command == install.INSTALL_LINE
        assert install.INSTALL_LINE.endswith("Staffroom@main")
        assert "fixed release" in here.update_hint() and install.INSTALL_LINE in here.update_hint()


def test_an_unreadable_receipt_shows_the_short_command(tmp_path: Path) -> None:
    package = uv_tool_package(tmp_path / "tools")
    (tmp_path / "tools" / "staffroom" / "uv-receipt.toml").write_text("[tool\n")
    assert install.detect(package).update_command == "uv tool upgrade staffroom"


def test_other_installs_are_not_checkouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    venv_pkg = tmp_path / "venv" / "lib" / "python3.12" / "site-packages" / "staffroom"
    venv_pkg.mkdir(parents=True)
    assert install.detect(venv_pkg).kind is InstallKind.OTHER  # pip, no uv receipt
    # A repository that is not this project, holding a src/staffroom folder.
    assert install.detect(checkout(tmp_path / "dotfiles", name="dotfiles")).kind is (
        InstallKind.OTHER
    )
    # This project's files with no .git: an unpacked sdist or a copied folder.
    assert install.detect(checkout(tmp_path / "sdist", git_dir=False)).kind is (InstallKind.OTHER)
    # An unreadable pyproject is not this project.
    broken = checkout(tmp_path / "broken")
    (tmp_path / "broken" / "pyproject.toml").write_text("[project\n")
    assert not install.detect(broken).is_checkout
    # A frozen bundle never counts as a checkout, whatever its folders look like.
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert install.detect(checkout(tmp_path / "frozen")).kind is InstallKind.OTHER


# -- update, CLI: no git for an installed copy ---------------------------


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Pretend the running copy is a uv tool install, and record (and refuse)
    every subprocess the update code tries to start."""
    package = uv_tool_package(tmp_path / "tools")
    monkeypatch.setattr(
        install,
        "detect",
        lambda package_dir=None: install.Installation(InstallKind.UV_TOOL, package),
    )
    calls: list[list[str]] = []

    def refuse(args: list[str], *_: object, **__: object) -> None:
        calls.append(list(args))
        raise AssertionError(f"an installed copy ran {args}")

    monkeypatch.setattr(update.subprocess, "run", refuse)
    return calls


def test_status_of_an_installed_copy_runs_no_git(installed: list[list[str]]) -> None:
    st = update.status()
    assert installed == []
    assert st.installed and "uv tool upgrade staffroom" in st.describe()
    assert not st.available and not st.can_apply and not st.error
    assert st.running_version(__version__) == __version__


def test_apply_on_an_installed_copy_refuses_before_git(installed: list[list[str]]) -> None:
    with pytest.raises(RuntimeError, match="uv tool upgrade staffroom"):
        update.apply()
    assert installed == []


@pytest.mark.parametrize("args", [["update"], ["update", "--check"]])
def test_staff_update_on_an_installed_copy_prints_one_line(
    installed: list[list[str]], args: list[str]
) -> None:
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert result.output.strip().splitlines() == [
        "This copy was installed with uv and never updates itself. "
        "To update it, quit Staffroom and run: uv tool upgrade staffroom"
    ]
    assert installed == []


def test_the_real_checkout_still_asks_git() -> None:
    """Unchanged for the owner's checkout: status reads the repository (no
    fetch here, so no network)."""
    st = update.status(fetch=False)
    assert st.installed == ""
    assert st.repo == REPO_ROOT


# -- end to end: a real process from an installed layout -----------------

SPY = """
import os, subprocess
_log = os.environ["STAFFROOM_TEST_SPY"]
_real = subprocess.Popen.__init__
def _spy(self, args, *a, **k):
    argv = [args] if isinstance(args, (str, bytes)) else list(args)
    with open(_log, "a") as fh:
        fh.write(" ".join(map(str, argv)) + "\\n")
    _real(self, args, *a, **k)
subprocess.Popen.__init__ = _spy
"""


def run_staff(
    package: Path, spy_dir: Path, cwd: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join([str(spy_dir), str(package.parent)]),
        "STAFFROOM_TEST_SPY": str(spy_dir / "calls.log"),
    }
    code = "import staffroom, sys; from staffroom.cli import main; main()"
    return subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.mark.parametrize("inside_repo", [True, False], ids=["inside-a-repo", "outside-any-repo"])
def test_installed_layout_never_touches_the_enclosing_repository(
    tmp_path: Path, inside_repo: bool
) -> None:
    """The bug as the audit found it: a uv tool folder inside a home folder
    kept as a git repository with a remote. ``staff update --check`` and
    ``staff update`` print the one line, exit 0, start no git process, and
    leave the repository byte-identical."""
    home = unrelated_repo(tmp_path) if inside_repo else tmp_path / "home"
    home.mkdir(exist_ok=True)
    package = uv_tool_package(home / ".local" / "share" / "uv" / "tools", package=PACKAGE)
    spy_dir = tmp_path / "spy"
    spy_dir.mkdir()
    (spy_dir / "sitecustomize.py").write_text(SPY)
    before = snapshot(home) if inside_repo else {}

    probe = run_staff(package, spy_dir, home, "version")
    assert probe.returncode == 0, probe.stderr
    for args in (["update", "--check"], ["update"]):
        result = run_staff(package, spy_dir, home, *args)
        assert result.returncode == 0, result.stderr
        assert "uv tool upgrade staffroom" in result.stdout
        assert "Traceback" not in result.stderr

    calls = (spy_dir / "calls.log").read_text() if (spy_dir / "calls.log").exists() else ""
    assert "git" not in calls, calls
    if inside_repo:
        assert snapshot(home) == before
        assert git("rev-list", "--count", "HEAD", cwd=home) == "1"


# -- the built wheel, installed with uv (network; the install-line CI job) --


@pytest.mark.skipif(
    os.environ.get("STAFFROOM_WHEEL_TEST") != "1" or shutil.which("uv") is None,
    reason="installs the built wheel with uv (needs the network); "
    "set STAFFROOM_WHEEL_TEST=1, as the install-line workflow does",
)
def test_built_wheel_installed_inside_a_repository_leaves_it_alone(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    home = unrelated_repo(tmp_path)
    dist = tmp_path / "dist"
    subprocess.run(
        [uv, "build", "--wheel", "-o", str(dist), str(REPO_ROOT)],
        check=True,
        capture_output=True,
        timeout=300,
    )
    wheel = next(dist.glob("staffroom-*.whl"))
    env = {
        **os.environ,
        "UV_TOOL_DIR": str(home / ".local" / "share" / "uv" / "tools"),
        "UV_TOOL_BIN_DIR": str(home / ".local" / "bin"),
        "STAFFROOM_HOME": str(tmp_path / "staffroom-home"),
    }
    python = getattr(sys, "_base_executable", sys.executable)
    subprocess.run(
        [uv, "tool", "install", "--python", python, str(wheel)],
        check=True,
        capture_output=True,
        env=env,
        cwd=str(home),
        timeout=600,
    )
    head, reflog = git("rev-parse", "HEAD", cwd=home), git("reflog", cwd=home)
    before = snapshot(home)
    staff = home / ".local" / "bin" / "staff"
    for args in (["update", "--check"], ["update"]):
        result = subprocess.run(
            [str(staff), *args],
            cwd=str(home),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        # Installed from a wheel file, uv cannot upgrade it in place: the one
        # command is the @main install line, read from uv's real receipt (#11).
        assert install.INSTALL_LINE in result.stdout, result.stdout
        assert "Traceback" not in result.stderr
    assert git("rev-parse", "HEAD", cwd=home) == head
    assert git("reflog", cwd=home) == reflog
    assert snapshot(home) == before
