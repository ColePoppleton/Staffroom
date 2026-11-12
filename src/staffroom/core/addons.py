"""Optional add-ons (#5): the heavy Qt modules a few features need, kept out
of the default install and added from Settings > Add-ons with no Terminal.

Each add-on is an extra of the ``staffroom`` package (``staffroom[web]``,
``staffroom[media]``), declared in ``pyproject.toml`` and pinned to the same
Qt release as the slim pair the app always has (PySide6-Essentials and
PySide6-Pdf). A plugin that cannot work without one says so with
``requires = ("web",)`` (see :mod:`staffroom.core.plugin`); the launcher then
lists it greyed with the install action instead of opening it.

This module is Qt-free and imports nothing heavy: whether an add-on is
installed is a look at the files of the ``PySide6`` package and its wheels'
metadata, never an import of the module itself.

Installing and removing go through :func:`plan` and :func:`apply`. The plan
follows how this copy was installed (:func:`staffroom.core.install.detect`):

* a **uv tool** is re-installed by uv from the same source its receipt
  records, with the new set of extras, into the same tool folder and with
  the same command links (``UV_TOOL_DIR`` and ``UV_TOOL_BIN_DIR`` are set
  from the running environment, so nothing else is ever touched);
* a **git checkout** (the thin launcher) runs ``uv sync`` with one
  ``--extra`` per add-on wanted;
* **anything else** (a PyInstaller bundle, pip into a venv) gets the manual
  route: the line to paste, never a guess.

The running copy is only changed once the change has worked somewhere
else. :func:`apply` first makes it in a throwaway environment (the same
command with ``UV_TOOL_DIR`` / ``UV_PROJECT_ENVIRONMENT`` pointing into a
temporary folder) and imports the Qt modules the app needs plus the add-ons
wanted in that environment's own Python. A failed download (no network, a
school proxy) or a set that does not import stops there, with the copy as it
was. Only then does it run the change for real, from uv's cache, and check
again; if that fails it puts the previous set back (uv has those wheels
already) and says so.

The Qt wheels share four files (``PySide6/__init__.py`` and friends), so
uninstalling an add-on's wheel deletes them from under the slim pair: the
package then imports as an empty namespace. Every change therefore also
re-installs the slim pair (``--reinstall-package``), which restores them from
the cache.

Tests never run uv: the installer takes a ``runner`` and the test suite
replaces the real one (``run_command``) with a guard.
"""

from __future__ import annotations

import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import cache
from importlib import machinery
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

from staffroom.core import install
from staffroom.core.log import get_logger

log = get_logger(__name__)

QT_VERSION = "6.12.0"
"""The Qt release every PySide6 wheel is pinned to (``pyproject.toml``)."""

SLIM_DISTRIBUTIONS = ("pyside6-essentials", "pyside6-pdf")
"""The Qt wheels every copy has. Re-installed with every add-on change."""

SLIM_MODULES = ("QtCore", "QtGui", "QtWidgets", "QtPdf", "QtPdfWidgets")
"""What a copy must still import after any add-on change."""


@dataclass(frozen=True)
class AddOn:
    """One optional add-on: an extra of the ``staffroom`` package."""

    name: str  # the extra and the ``requires`` name: "web"
    title: str  # "Web"
    enables: str  # what it is for, one sentence for a teacher
    modules: tuple[str, ...]  # the PySide6 modules it brings (probed on disk)
    distributions: tuple[str, ...]  # the wheels the extra installs
    download_mb: int  # about how much the first install downloads
    disk_mb: int  # about how much more space it takes

    @property
    def label(self) -> str:
        """``the Web add-on``: how sentences name it."""
        return f"the {self.title} add-on"

    @property
    def sentence_label(self) -> str:
        """``The Web add-on``, to start a sentence."""
        return f"The {self.title} add-on"

    def size_text(self) -> str:
        return f"About {self.download_mb} MB to download, {self.disk_mb} MB on disk."


ADDONS: dict[str, AddOn] = {
    addon.name: addon
    for addon in (
        AddOn(
            name="web",
            title="Web",
            enables=(
                "A full web browser engine, for tools that show web pages the way a browser does."
            ),
            modules=("QtWebEngineCore", "QtWebEngineWidgets"),
            distributions=("pyside6-addons", "pyside6-webengine"),
            download_mb=340,
            disk_mb=900,
        ),
        AddOn(
            name="media",
            title="Media",
            enables="Sound and video playback, for tools that play audio or video clips.",
            modules=("QtMultimedia", "QtMultimediaWidgets"),
            distributions=("pyside6-addons",),
            download_mb=90,
            disk_mb=245,
        ),
    )
}
"""Every add-on, in the order Settings lists them. The names are the extras
in ``pyproject.toml`` (a test keeps the two in step)."""


def get(name: str) -> AddOn:
    """The add-on called ``name``; KeyError for an unknown one."""
    return ADDONS[name]


def unknown(names: Iterable[str]) -> list[str]:
    """The names in ``names`` that are not add-ons."""
    return [n for n in names if n not in ADDONS]


# -- what is installed ---------------------------------------------------------


def _pyside_dirs() -> list[Path]:
    """The ``PySide6`` package folders on ``sys.path``, found without
    importing PySide6 (a top-level ``find_spec`` runs no package code)."""
    try:
        spec = importlib.util.find_spec("PySide6")
    except (ImportError, ValueError):
        return []
    if spec is None or spec.submodule_search_locations is None:
        return []
    return [Path(p) for p in spec.submodule_search_locations]


def _has_module(dirs: Sequence[Path], module: str) -> bool:
    """A compiled ``PySide6.<module>`` is on disk (``QtMultimedia.abi3.so``)."""
    return any(
        (folder / f"{module}{suffix}").is_file()
        for folder in dirs
        for suffix in machinery.EXTENSION_SUFFIXES
    )


def _qt_release(distribution: str) -> str | None:
    """``6.12.0`` for a wheel at ``6.12.0`` or ``6.12.0.140``; None when it
    is not installed."""
    try:
        return ".".join(version(distribution).split(".")[:3])
    except PackageNotFoundError:
        return None


def probe(addon: AddOn) -> bool:
    """Whether ``addon`` is installed and usable: each of its modules is on
    disk, and its wheels are at the same Qt release as the slim pair (a
    mismatched pair crashes on import). Imports nothing."""
    dirs = _pyside_dirs()
    if not dirs or not all(_has_module(dirs, m) for m in addon.modules):
        return False
    slim = _qt_release(SLIM_DISTRIBUTIONS[0])
    for dist in addon.distributions:
        release = _qt_release(dist)
        if release is not None and slim is not None and release != slim:
            return False
    return True


@cache
def is_installed(name: str) -> bool:
    """Whether the add-on ``name`` is installed in the running copy. Cached:
    an install only takes effect after a restart, so the answer stays the
    one the app started with. Unknown names are never installed."""
    addon = ADDONS.get(name)
    return addon is not None and probe(addon)


def refresh() -> None:
    """Forget the cached answers (tests, and after a change in the CLI)."""
    is_installed.cache_clear()


def installed() -> frozenset[str]:
    """The names of the add-ons installed in the running copy."""
    return frozenset(name for name in ADDONS if is_installed(name))


def missing(names: Iterable[str]) -> tuple[AddOn, ...]:
    """The add-ons among ``names`` that are not installed; an unknown name
    counts as missing (it can never be installed)."""
    found: list[AddOn] = []
    for name in names:
        if not is_installed(name):
            found.append(ADDONS.get(name) or AddOn(name, name, "", (), (), 0, 0))
    return tuple(found)


def needs_text(addons: Sequence[AddOn]) -> str:
    """``Needs the Web add-on`` (or ``…the Web and Media add-ons``)."""
    titles = [a.title for a in addons]
    if len(titles) == 1:
        return f"Needs the {titles[0]} add-on"
    return f"Needs the {', '.join(titles[:-1])} and {titles[-1]} add-ons"


def included_in(name: str, others: Iterable[str]) -> AddOn | None:
    """The add-on among ``others`` whose wheels already include every wheel
    of ``name`` (Media's are part of Web's), so removing ``name`` alone
    would change nothing; None when there is no such add-on."""
    addon = ADDONS[name]
    for other in others:
        if other != name and set(addon.distributions) <= set(ADDONS[other].distributions):
            return ADDONS[other]
    return None


# -- how to change them --------------------------------------------------------


@dataclass(frozen=True)
class Plan:
    """How to give this copy exactly the add-ons ``wanted``.

    ``command`` is empty when this copy cannot change itself; ``manual`` is
    then the one line to paste, or ``""`` when there is none either. ``env``
    holds the variables set on top of the process's own."""

    kind: install.InstallKind
    wanted: frozenset[str]
    command: tuple[str, ...] = ()
    cwd: Path | None = None
    env: Mapping[str, str] = field(default_factory=dict)
    manual: str = ""
    why_manual: str = ""

    @property
    def runnable(self) -> bool:
        return bool(self.command)

    def line(self) -> str:
        """The command as one line to paste into Terminal, with its folder
        and variables; ``""`` when there is no command."""
        if not self.command:
            return ""
        parts = [f"{k}={shlex.quote(v)}" for k, v in sorted(self.env.items())]
        parts.append(shlex.join(self.command))
        line = " ".join(parts)
        return f"cd {shlex.quote(str(self.cwd))} && {line}" if self.cwd else line

    def trial(self, folder: Path) -> tuple[Plan, Path] | None:
        """The same change made in a throwaway environment under ``folder``,
        and that environment's Python; None when there is nothing to run.
        Nothing outside ``folder`` changes (uv's cache aside)."""
        if not self.command:
            return None
        if self.kind is install.InstallKind.CHECKOUT:
            env = {"UV_PROJECT_ENVIRONMENT": str(folder / "env")}
            python = folder / "env" / "bin" / "python"
        else:
            env = {"UV_TOOL_DIR": str(folder / "tools"), "UV_TOOL_BIN_DIR": str(folder / "bin")}
            python = folder / "tools" / install.PROJECT_NAME / "bin" / "python"
        return replace(self, env={**self.env, **env}), python


def extras_spec(wanted: Iterable[str]) -> str:
    """``[media,web]``, or ``""`` for none."""
    names = sorted(wanted)
    return f"[{','.join(names)}]" if names else ""


def manual_line(wanted: Iterable[str]) -> str:
    """The install line with the add-ons, for a copy that cannot change
    itself: a fresh ``uv tool install`` of the released branch."""
    spec = f"staffroom{extras_spec(wanted)} @ git+https://github.com/ColePoppleton/Staffroom@main"
    return f"uv tool install --python 3.12 '{spec}'"


def find_uv() -> str | None:
    """The ``uv`` program: on ``PATH``, else where its installer puts it (an
    app opened from Finder has a short ``PATH``)."""
    from staffroom.core.update import find_uv as known_places

    return shutil.which("uv") or known_places()


def plan(
    wanted: Iterable[str],
    installation: install.Installation | None = None,
    *,
    uv: str | None = None,
) -> Plan:
    """The plan that leaves this copy with exactly the add-ons ``wanted``.
    ``installation`` defaults to the running copy, ``uv`` to :func:`find_uv`."""
    names = frozenset(wanted)
    bad = unknown(names)
    if bad:
        msg = f"unknown add-on {bad[0]!r}"
        raise KeyError(msg)
    here = installation or install.detect()
    manual = manual_line(names)
    if here.kind is install.InstallKind.OTHER:
        return Plan(
            here.kind,
            names,
            manual=manual,
            why_manual=(
                "This copy of Staffroom cannot add to itself (it was not installed with uv "
                "or from a git checkout). To have add-ons, install it with uv instead:"
            ),
        )
    if here.kind is install.InstallKind.CHECKOUT:
        root = here.root or here.package_dir.parents[1]
        extras = [arg for name in sorted(names) for arg in ("--extra", name)]
        manual = f"cd {shlex.quote(str(root))} && {shlex.join(['uv', 'sync', *extras])}"
    uv = uv or find_uv()
    if uv is None:
        return Plan(
            here.kind,
            names,
            manual=manual,
            why_manual=(
                "Staffroom could not find uv, the program it was installed with; quit "
                "Staffroom and run this line in Terminal instead:"
            ),
        )
    if here.kind is install.InstallKind.CHECKOUT:
        command = (uv, "sync", *extras, *_reinstall_slim())
        return Plan(here.kind, names, command, cwd=root, manual=manual)
    return _uv_tool_plan(here, names, uv, manual)


def _reinstall_slim() -> list[str]:
    args: list[str] = []
    for dist in SLIM_DISTRIBUTIONS:
        args += ["--reinstall-package", dist]
    return args


def _uv_tool_plan(here: install.Installation, names: frozenset[str], uv: str, manual: str) -> Plan:
    receipt_path = find_receipt(here.package_dir)
    receipt = read_receipt(receipt_path) if receipt_path else None
    source = receipt.requirement(names) if receipt else None
    if receipt is None or receipt_path is None or source is None:
        return Plan(
            here.kind,
            names,
            manual=manual,
            why_manual="Staffroom could not read how uv installed it.",
        )
    command = [uv, "tool", "install"]
    if receipt.python:
        command += ["--python", receipt.python]
    for other in receipt.others:
        command += ["--with", other]
    command += _reinstall_slim()
    command.append(source)
    env = {"UV_TOOL_DIR": str(receipt_path.parent.parent)}
    if receipt.bin_dir is not None:
        env["UV_TOOL_BIN_DIR"] = str(receipt.bin_dir)
    return Plan(here.kind, names, tuple(command), env=env)


def find_receipt(package_dir: Path) -> Path | None:
    """uv's ``uv-receipt.toml`` at the root of the environment holding
    ``package_dir`` (``<env>/lib/pythonX.Y/site-packages/staffroom``)."""
    for folder in package_dir.parents:
        candidate = folder / install.UV_RECEIPT
        if candidate.is_file():
            return candidate
    return None


@dataclass(frozen=True)
class Receipt:
    """What a uv tool receipt says about how Staffroom was installed."""

    source: Mapping[str, object]  # the ``staffroom`` requirement as uv wrote it
    others: tuple[str, ...] = ()  # other requirements (``--with``), as PEP 508 strings
    python: str = ""
    bin_dir: Path | None = None  # where uv linked ``staff`` and ``staffroom``

    def requirement(self, extras: Iterable[str]) -> str | None:
        """The ``staffroom`` requirement with ``extras``, from the same
        source as before (same git revision, wheel or folder); None for a
        source this does not understand."""
        return requirement_string(self.source, extras)


def read_receipt(path: Path) -> Receipt | None:
    """The receipt at ``path``, or None when it cannot be read or names no
    ``staffroom`` requirement."""
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    requirements = tool.get("requirements")
    if not isinstance(requirements, list):
        return None
    source: Mapping[str, object] | None = None
    others: list[str] = []
    for req in requirements:
        if not isinstance(req, dict):
            return None
        if req.get("name") == install.PROJECT_NAME and source is None:
            source = req
            continue
        other = requirement_string(req, req.get("extras") or ())
        if other is None:
            return None
        others.append(other)
    if source is None:
        return None
    python = tool.get("python")
    bin_dir: Path | None = None
    entrypoints = tool.get("entrypoints")
    if isinstance(entrypoints, list):
        for entry in entrypoints:
            where = entry.get("install-path") if isinstance(entry, dict) else None
            if isinstance(where, str) and where:
                bin_dir = Path(where).parent
                break
    return Receipt(source, tuple(others), python if isinstance(python, str) else "", bin_dir)


def requirement_string(req: Mapping[str, object], extras: Iterable[str]) -> str | None:
    """A uv receipt requirement as a PEP 508 string with ``extras``:
    ``staffroom[web] @ git+https://…@main``. None for an unfamiliar shape."""
    name = req.get("name")
    if not isinstance(name, str) or not name:
        return None
    head = f"{name}{extras_spec(extras)}"
    git = req.get("git")
    if isinstance(git, str):
        parts = urlsplit(git)
        query = parse_qs(parts.query)
        rev = query.get("rev", query.get("tag", query.get("branch", [""])))[0]
        base = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        target = f"git+{base}@{rev}" if rev else f"git+{base}"
        subdirectory = req.get("subdirectory")
        if isinstance(subdirectory, str) and subdirectory:
            target += f"#subdirectory={subdirectory}"
        return f"{head} @ {target}"
    for key in ("path", "directory"):
        where = req.get(key)
        if isinstance(where, str) and where:
            return f"{head} @ {Path(where).resolve().as_uri()}"
    url = req.get("url")
    if isinstance(url, str) and url:
        return f"{head} @ {url}"
    if any(k in req for k in ("editable", "virtual")):
        return None
    specifier = req.get("specifier")
    return f"{head}{specifier}" if isinstance(specifier, str) else head


# -- running a plan ------------------------------------------------------------

#: ``runner(command, cwd, env, line) -> exit code``. ``line`` gets each line
#: of output as it comes. The real one is :func:`run_command`; tests pass a
#: fake (and the test suite replaces this one with a guard).
Runner = Callable[[Sequence[str], Path | None, Mapping[str, str], Callable[[str], None]], int]

TIMEOUT = 30 * 60  # seconds; the Web add-on is a few hundred MB on a school network


def run_command(
    command: Sequence[str], cwd: Path | None, env: Mapping[str, str], line: Callable[[str], None]
) -> int:
    """Run ``command``, sending each output line to ``line``; its exit code.
    127 when the program cannot be started, 124 when it runs too long."""
    full_env = {**os.environ, **env}
    try:
        proc = subprocess.Popen(
            list(command),
            cwd=str(cwd) if cwd else None,
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        line(str(exc))
        return 127
    assert proc.stdout is not None
    for text in proc.stdout:
        line(text.rstrip("\n"))
    try:
        return proc.wait(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        line("timed out")
        return 124


real_run_command = run_command
"""The real runner under a second name: the test suite replaces
``run_command`` with a guard, and tests of the runner itself call this."""


def verify_command(wanted: Iterable[str], python: str | None = None) -> tuple[str, ...]:
    """A command that imports, in the changed environment's own Python, the
    Qt modules every copy needs and each wanted add-on's modules, and fails
    when ``PySide6`` lost its package files (see the module docstring)."""
    modules = list(SLIM_MODULES)
    for name in sorted(wanted):
        modules += ADDONS[name].modules
    code = (
        "import importlib, PySide6\n"
        "assert PySide6.__file__, 'PySide6 lost its package files'\n"
        f"for m in {modules!r}:\n"
        "    importlib.import_module('PySide6.' + m)\n"
    )
    return (python or sys.executable, "-c", code)


@dataclass(frozen=True)
class Outcome:
    """How a change went: ``message`` is one sentence for the teacher."""

    ok: bool
    message: str
    restart: bool = False  # the copy changed: a restart picks it up
    command: str = ""  # a line to paste when the teacher has to finish by hand


NO_NETWORK = (
    "Staffroom could not download the add-on because this Mac could not reach the internet; "
    "try again when it is online."
)
BLOCKED = (
    "This network blocked the download (a school proxy or web filter, most likely); try again "
    "on another network, or ask IT to allow pypi.org, files.pythonhosted.org and github.com."
)
NO_SPACE = "There is not enough free space on this Mac for the add-on; free some up and try again."
TOO_SLOW = "The download took too long and was stopped; try again on a faster network."
NO_UV = (
    "Staffroom could not start uv, the program it was installed with; quit Staffroom and run "
    "the line below in Terminal instead."
)
FAILED = "The add-on could not be changed; Details has the installer's messages."
WOULD_BREAK = (
    "The add-on installed but did not start in a test copy, so Staffroom left this one as it "
    "was; Details has the installer's messages."
)
BROKEN = (
    "The change did not work, so Staffroom put the previous add-ons back; Details has the "
    "installer's messages."
)
STUCK = (
    "The change did not work and the previous add-ons could not be put back either; "
    "run the line below in Terminal to repair this copy."
)

_NETWORK_HINTS = (
    "dns error",
    "failed to lookup address",
    "could not resolve host",
    "network is unreachable",
    "no route to host",
    "connection refused",
    "tcp connect error",
    "error sending request",
    "failed to fetch",
    "failed to download",
    "connection reset",
    "offline",
    "network was disabled",
)
_BLOCKED_HINTS = (
    "certificate",
    "unknownissuer",
    "proxy",
    "tunnel error",
    "407",
    "403 forbidden",
    "tls handshake",
    "ssl",
)


_STEPS = ("Resolved", "Downloading", "Downloaded", "Prepared", "Uninstalled", "Installed")
"""uv's output lines that make a good progress line (it prints them even
when its output is not a terminal)."""


def explain(exit_code: int, output: str) -> str:
    """One sentence for a failed install, read from uv's output."""
    text = output.casefold()
    if exit_code == 127:
        return NO_UV
    if exit_code == 124 or "timed out" in text or "operation timed out" in text:
        return TOO_SLOW
    if "no space left on device" in text:
        return NO_SPACE
    if any(hint in text for hint in _BLOCKED_HINTS):
        return BLOCKED
    if any(hint in text for hint in _NETWORK_HINTS):
        return NO_NETWORK
    return FAILED


def change_text(before: frozenset[str], after: frozenset[str]) -> str:
    """``Installed the Web add-on.`` / ``Removed the Media add-on.``"""
    added = [ADDONS[n].title for n in ADDONS if n in after - before]
    removed = [ADDONS[n].title for n in ADDONS if n in before - after]
    parts = []
    if added:
        parts.append(f"Installed the {' and '.join(added)} add-on{'s' if len(added) > 1 else ''}")
    if removed:
        s = "s" if len(removed) > 1 else ""
        parts.append(f"removed the {' and '.join(removed)} add-on{s}")
    if not parts:
        return "Nothing to change."
    sentence = "; ".join(parts)
    return sentence[0].upper() + sentence[1:] + ". Restart Staffroom to use it."


def change(
    wanted: Iterable[str],
    *,
    installation: install.Installation | None = None,
    uv: str | None = None,
    runner: Runner | None = None,
    log_line: Callable[[str], None] = lambda _m: None,
    progress: Callable[[str], None] = lambda _m: None,
) -> Outcome:
    """Leave this copy with exactly the add-ons ``wanted``: plan it from how
    the copy was installed, run it, check it. See :func:`apply`."""
    target = plan(wanted, installation, uv=uv)
    previous = plan(installed(), installation, uv=uv)
    return apply(target, previous, runner=runner, log_line=log_line, progress=progress)


def apply(
    target: Plan,
    previous: Plan,
    *,
    runner: Runner | None = None,
    log_line: Callable[[str], None] = lambda _m: None,
    progress: Callable[[str], None] = lambda _m: None,
    scratch: Path | None = None,
) -> Outcome:
    """Carry out ``target`` and check the result. It is tried first in a
    throwaway environment in a temporary folder (inside ``scratch`` when
    given) and the running copy is left alone unless that works.
    ``previous`` is the plan for what the copy had: it is run to put that
    back when the real change does not import. ``log_line`` gets every line
    of output (the Details log), ``progress`` a short line for each step.
    Never raises for a failed install: the outcome says it."""
    run = runner or run_command
    if not target.runnable:
        return Outcome(False, target.why_manual or FAILED, command=target.manual)
    before = previous.wanted
    lines: list[str] = []

    def keep(text: str) -> None:
        lines.append(text)
        log_line(text)
        step = text.strip()
        if step.startswith(_STEPS):
            progress(step)

    def failed(code: int) -> Outcome:
        message = explain(code, "\n".join(lines))
        log.warning("add-on change failed (exit %s): %s", code, message)
        return Outcome(False, message, command=target.manual if code == 127 else "")

    log.info("add-ons %s -> %s: %s", sorted(before), sorted(target.wanted), target.command)
    progress("Downloading…" if target.wanted - before else "Preparing…")
    folder = Path(tempfile.mkdtemp(prefix="staffroom-addons-", dir=scratch))
    try:
        trial = target.trial(folder)
        assert trial is not None  # target is runnable
        test_plan, test_python = trial
        code = run(test_plan.command, test_plan.cwd, test_plan.env, keep)
        if code != 0:
            return failed(code)
        progress("Checking it works…")
        if run(verify_command(target.wanted, str(test_python)), None, {}, keep) != 0:
            log.error("the add-on change does not import in a test copy; nothing changed")
            return Outcome(False, WOULD_BREAK)
    finally:
        shutil.rmtree(folder, ignore_errors=True)

    progress("Installing…" if target.wanted - before else "Removing…")
    code = run(target.command, target.cwd, target.env, keep)
    if code != 0:
        return failed(code)
    progress("Checking it works…")
    if run(verify_command(target.wanted), None, {}, keep) == 0:
        return Outcome(True, change_text(before, target.wanted), restart=True)
    log.error("the add-on change installed but does not import; restoring %s", sorted(before))
    progress("Putting the previous add-ons back…")
    if (
        previous.runnable
        and run(previous.command, previous.cwd, previous.env, keep) == 0
        and run(verify_command(before), None, {}, keep) == 0
    ):
        return Outcome(False, BROKEN, restart=True)
    return Outcome(False, STUCK, restart=True, command=previous.line() or previous.manual)
