"""Staffroom installs only two Qt wheels, not the whole of PySide6 (#4).

The ``pyside6`` meta-package pulls in PySide6-Addons and QtWebEngine: about
1 GB a colleague downloads and never uses. The app depends on
``PySide6-Essentials`` (QtCore, QtGui, QtWidgets, QtSvg, QtPrintSupport, ...)
and ``PySide6-Pdf`` (QtPdf, QtPdfWidgets) instead.

A Qt module outside those two would still import on a machine that happens to
have the full package, and then fail on a fresh install. So every Python file
under ``src/`` (and the tests, scripts and packaging that run from the repo)
is scanned for PySide6 imports, and each must be a module one of the two
distributions ships. The set comes from the installed wheels' file lists, so
it follows the pinned version instead of a hand-kept list.
"""

from __future__ import annotations

import ast
import re
import tomllib
from importlib.metadata import PackageNotFoundError, files
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCANNED_DIRS = ("src", "tests", "scripts", "packaging")

SLIM_DISTRIBUTIONS = ("pyside6-essentials", "pyside6-pdf")
FULL_DISTRIBUTIONS = ("pyside6", "pyside6-addons", "pyside6-webengine")

# What the app imports today. If one of these ever leaves the two wheels the
# dependency line must change, not the code silently start needing more.
USED = {
    "QtCore",
    "QtGui",
    "QtWidgets",
    "QtSvg",
    "QtPrintSupport",
    "QtPdf",
    "QtPdfWidgets",
}

_REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)$")


def provided_modules() -> set[str]:
    """Qt modules shipped by the installed Essentials and Pdf wheels."""
    modules: set[str] = set()
    for dist in SLIM_DISTRIBUTIONS:
        try:
            dist_files = files(dist) or []
        except PackageNotFoundError:  # reported by test_slim_wheels_are_what_is_installed
            continue
        for f in dist_files:
            parts = f.parts
            if len(parts) == 2 and parts[0] == "PySide6" and parts[1].startswith("Qt"):
                modules.add(parts[1].split(".")[0])
    return modules


def _is_dynamic_import(func: ast.expr) -> bool:
    if isinstance(func, ast.Name):
        return func.id in {"import_module", "__import__"}
    return isinstance(func, ast.Attribute) and func.attr == "import_module"


def qt_imports(source: str) -> list[tuple[int, str]]:
    """Each PySide6 Qt module ``source`` imports, as ``(line, "QtName")``.

    Covers ``import PySide6.QtX``, ``from PySide6.QtX[.sub] import ...``,
    ``from PySide6 import QtX`` and ``importlib.import_module("PySide6.QtX")``.
    """
    found: list[tuple[int, str]] = []

    def add(line: int, dotted: str) -> None:
        parts = dotted.split(".")
        if parts[0] == "PySide6" and len(parts) > 1 and parts[1].startswith("Qt"):
            found.append((line, parts[1]))

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                add(node.lineno, alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module == "PySide6":
                for alias in node.names:
                    add(node.lineno, f"PySide6.{alias.name}")
            else:
                add(node.lineno, node.module)
        elif (
            isinstance(node, ast.Call)
            and _is_dynamic_import(node.func)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            add(node.lineno, node.args[0].value)
    return found


def python_files() -> list[Path]:
    paths = [ROOT / "conftest.py"]
    for name in SCANNED_DIRS:
        paths.extend(sorted((ROOT / name).rglob("*.py")))
    return [p for p in paths if p.is_file()]


def _dependencies() -> dict[str, str]:
    """``{normalised name: specifier}`` from ``[project].dependencies``."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    deps: dict[str, str] = {}
    for line in project["dependencies"]:
        match = _REQUIREMENT.match(line)
        assert match, line
        deps[re.sub(r"[-_.]+", "-", match.group(1)).lower()] = match.group(2).strip()
    return deps


def test_depends_on_the_slim_wheels_at_one_version() -> None:
    deps = _dependencies()
    full = sorted(set(FULL_DISTRIBUTIONS) & deps.keys())
    assert not full, f"depend on {SLIM_DISTRIBUTIONS}, not {full} (about 1 GB more)"
    missing = [d for d in SLIM_DISTRIBUTIONS if d not in deps]
    assert not missing, f"pyproject.toml must depend on {missing}"
    pins = {deps[d] for d in SLIM_DISTRIBUTIONS}
    assert len(pins) == 1, f"pin {SLIM_DISTRIBUTIONS} to the same version, got {sorted(pins)}"
    assert next(iter(pins)).startswith("=="), "pin the Qt wheels exactly, not a range"


def test_slim_wheels_are_what_is_installed() -> None:
    for dist in SLIM_DISTRIBUTIONS:
        try:
            files(dist)
        except PackageNotFoundError:
            pytest.fail(f"{dist} is not installed; run `uv sync`")
    for dist in FULL_DISTRIBUTIONS:
        with pytest.raises(PackageNotFoundError):
            files(dist)  # a stale full install would hide a missing module


def test_every_module_the_app_uses_is_provided() -> None:
    missing = USED - provided_modules()
    assert not missing, f"{sorted(missing)} not in {SLIM_DISTRIBUTIONS}"


def test_imports_only_provided_qt_modules() -> None:
    provided = provided_modules()
    bad = [
        f"{path.relative_to(ROOT)} line {line}: PySide6.{name}"
        for path in python_files()
        for line, name in qt_imports(path.read_text(encoding="utf-8"))
        if name not in provided
    ]
    assert not bad, (
        "these import Qt modules that PySide6-Essentials and PySide6-Pdf do not ship, "
        f"so a fresh install would fail: {bad}"
    )


def test_scan_covers_the_app() -> None:
    # Guard against the scan silently finding nothing (a moved src/, say).
    seen = {name for path in python_files() for _, name in qt_imports(path.read_text("utf-8"))}
    assert seen >= USED, sorted(USED - seen)


@pytest.mark.parametrize(
    ("snippet", "expected"),
    [
        ("import PySide6.QtWebEngineWidgets", ["QtWebEngineWidgets"]),
        ("import PySide6.QtMultimedia as mm", ["QtMultimedia"]),
        ("from PySide6.QtCharts import QChart", ["QtCharts"]),
        ("from PySide6 import QtCore, Qt3DCore", ["QtCore", "Qt3DCore"]),
        ("from PySide6.QtCore import Qt", ["QtCore"]),
        ('importlib.import_module("PySide6.QtWebEngineCore")', ["QtWebEngineCore"]),
        ('__import__("PySide6.QtQuick3D")', ["QtQuick3D"]),
        ("from PySide6 import __version__", []),
        ("import shiboken6", []),
        ("from .QtCore import x", []),
    ],
)
def test_scan_finds_qt_imports(snippet: str, expected: list[str]) -> None:
    assert [name for _, name in qt_imports(snippet)] == expected


def test_addons_modules_are_not_provided() -> None:
    # The scan is only useful if the set really is the slim one.
    provided = provided_modules()
    assert not {"QtWebEngineCore", "QtMultimedia", "QtCharts", "Qt3DCore"} & provided
