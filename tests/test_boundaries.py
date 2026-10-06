"""Architectural rules, enforced by scanning source. import-linter checks the
same thing at lint time; this makes the rule fail loudly in the test run too.

* tools/ never import PySide6/shiboken6 or the shell.
* logic.py never imports I/O, typer or Qt.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import teaching_tools
import teaching_tools.tools as tools_pkg

PKG = Path(teaching_tools.__file__).parent
TOOLS = Path(tools_pkg.__file__).parent

QT_PREFIXES = ("PySide6", "shiboken6", "PyQt5", "PyQt6", "teaching_tools.shell")
IO_MODULES = {
    "os",
    "io",
    "sys",
    "csv",
    "json",
    "pathlib",
    "shutil",
    "subprocess",
    "typer",
    "openpyxl",
    "sqlite3",
    "requests",
    "teaching_tools.core.csvio",
    "teaching_tools.core.config",
    "teaching_tools.core.paths",
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def tool_files() -> list[Path]:
    return sorted(p for p in TOOLS.rglob("*.py"))


@pytest.mark.parametrize("path", tool_files(), ids=lambda p: str(p.relative_to(PKG)))
def test_tools_never_import_qt(path: Path) -> None:
    bad = {m for m in imported_modules(path) if m.startswith(QT_PREFIXES)}
    assert not bad, f"{path.relative_to(PKG)} imports Qt/shell: {sorted(bad)}"


@pytest.mark.parametrize(
    "path", [p for p in tool_files() if p.name == "logic.py"], ids=lambda p: p.parent.name
)
def test_logic_is_pure(path: Path) -> None:
    bad = {m for m in imported_modules(path) if m in IO_MODULES or m.split(".")[0] in IO_MODULES}
    assert not bad, f"{path.relative_to(PKG)} does I/O: {sorted(bad)}"


def test_core_never_imports_qt_or_tools() -> None:
    for path in (PKG / "core").rglob("*.py"):
        mods = imported_modules(path)
        bad = {m for m in mods if m.startswith((*QT_PREFIXES, "teaching_tools.tools", "typer"))}
        assert not bad, f"{path.relative_to(PKG)}: {sorted(bad)}"
