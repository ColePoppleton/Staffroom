"""Architectural rules, enforced by scanning source. import-linter checks the
same thing at lint time; this makes the rule fail loudly in the test run too.

* tools/ never import PySide6/shiboken6 or the shell.
* logic.py never imports I/O, typer or Qt.
* tools/ read tables (.csv/.xlsx) only through core.csvio.read_table, the
  enforcement point for the no-pupil-data rule (#68). A static scan: any
  parser reference (csv.reader, openpyxl.load_workbook, csvio's unfiltered
  read_csv/read_xlsx) and any raw open()/read_text()/read_bytes() of a path
  that is visibly a table file, either by a ".csv"/".xlsx" literal or because
  it came from one of the tool's own table pickers. Reading .md or .py text,
  and writing tables, are fine.
"""

from __future__ import annotations

import ast
import dataclasses
from collections.abc import Collection
from pathlib import Path

import pytest

import staffroom
import staffroom.tools as tools_pkg
from staffroom.core.csvio import TABLE_EXTENSIONS
from staffroom.core.discovery import discover_plugins
from staffroom.core.panel import FilePicker, ResourcePicker

PKG = Path(staffroom.__file__).parent
TOOLS = Path(tools_pkg.__file__).parent

QT_PREFIXES = ("PySide6", "shiboken6", "PyQt5", "PyQt6", "staffroom.shell")
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
    "staffroom.core.csvio",
    "staffroom.core.config",
    "staffroom.core.paths",
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
        bad = {m for m in mods if m.startswith((*QT_PREFIXES, "staffroom.tools", "typer"))}
        assert not bad, f"{path.relative_to(PKG)}: {sorted(bad)}"


# ---------------------------------------------------------------- tables via csvio
# Readers that bypass core.csvio.read_table and so the identifier filter.
TABLE_PARSERS = {
    ("csv", "reader"),
    ("csv", "DictReader"),
    ("openpyxl", "load_workbook"),
    ("openpyxl.reader", "*"),
    ("openpyxl.reader.excel", "*"),
}
TABLE_READER_NAMES = {"load_workbook", "read_csv", "read_xlsx", "read_excel"}
RAW_READ_METHODS = {"open", "read_text", "read_bytes"}


def _mentions_table_suffix(node: ast.AST) -> bool:
    return any(
        isinstance(n, ast.Constant)
        and isinstance(n.value, str)
        and n.value.lower().endswith(TABLE_EXTENSIONS)
        for n in ast.walk(node)
    )


def _is_write_mode(call: ast.Call, mode_index: int) -> bool:
    mode: ast.expr | None = None
    if len(call.args) > mode_index:
        mode = call.args[mode_index]
    for kw in call.keywords:
        if kw.arg == "mode":
            mode = kw.value
    return (
        isinstance(mode, ast.Constant)
        and isinstance(mode.value, str)
        and any(ch in mode.value for ch in "wax")
    )


def _picked_names(tree: ast.AST, keys: set[str]) -> set[str]:
    """Names bound to ``inputs.get("key")`` or ``inputs["key"]`` for a table key."""

    def key_of(value: ast.expr) -> str | None:
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "get"
            and value.args
            and isinstance(value.args[0], ast.Constant)
        ):
            return str(value.args[0].value)
        if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Constant):
            return str(value.slice.value)
        return None

    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign | ast.AnnAssign)
            and node.value is not None
            and key_of(node.value) in keys
        ):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names.update(t.id for t in targets if isinstance(t, ast.Name))
    return names


def table_reads(source: str, table_keys: Collection[str] = ()) -> list[str]:
    """Each place in ``source`` that reads a table without core.csvio, as
    ``"line N: what"``."""
    tree = ast.parse(source)
    picked = _picked_names(tree, set(table_keys))
    found: list[str] = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                parser = {(node.module, alias.name), (node.module, "*")} & TABLE_PARSERS
                if parser or alias.name in TABLE_READER_NAMES:
                    found.append(f"line {line}: imports {node.module}.{alias.name}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if (alias.name, "*") in TABLE_PARSERS:
                    found.append(f"line {line}: imports {alias.name}")
        elif isinstance(node, ast.Attribute):
            owner = ast.unparse(node.value)
            if (owner, node.attr) in TABLE_PARSERS or node.attr in TABLE_READER_NAMES:
                found.append(f"line {line}: uses {owner}.{node.attr}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "open" and node.args:
                target: ast.expr = node.args[0]
                writing = _is_write_mode(node, 1)
            elif isinstance(func, ast.Attribute) and func.attr in RAW_READ_METHODS:
                target = func.value
                writing = func.attr == "open" and _is_write_mode(node, 0)
            else:
                continue
            is_table = _mentions_table_suffix(target) or (
                isinstance(target, ast.Name) and target.id in picked
            )
            if is_table and not writing:
                found.append(f"line {line}: raw read of {ast.unparse(target)}")
    return found


def _table_picker_keys(spec: object) -> set[str]:
    """Keys of FilePicker / ResourcePicker inputs that pick a table file."""
    keys: set[str] = set()
    pending: list[object] = [spec]
    while pending:
        item = pending.pop()
        if isinstance(item, FilePicker):
            if item.mode == "open" and any(
                ext in f.lower() for f in item.filters for ext in TABLE_EXTENSIONS
            ):
                keys.add(item.key)
        elif isinstance(item, ResourcePicker):
            if any(ext in TABLE_EXTENSIONS for ext in item.extensions):
                keys.add(item.key)
        elif dataclasses.is_dataclass(item) and not isinstance(item, type):
            pending.extend(getattr(item, f.name) for f in dataclasses.fields(item))
        elif isinstance(item, list | tuple):
            pending.extend(item)
    return keys


def _tool_table_keys() -> dict[str, set[str]]:
    return {p.name: _table_picker_keys(p.panel_spec()) for p in discover_plugins()}


def tool_source_files() -> list[Path]:
    return [p for p in tool_files() if "tests" not in p.relative_to(TOOLS).parts]


@pytest.mark.parametrize("path", tool_source_files(), ids=lambda p: str(p.relative_to(PKG)))
def test_tools_read_tables_only_through_csvio(path: Path) -> None:
    tool = path.relative_to(TOOLS).parts[0]
    keys = _tool_table_keys().get(tool, set())
    bad = table_reads(path.read_text(encoding="utf-8"), keys)
    assert not bad, (
        f"{path.relative_to(PKG)} reads a table without core.csvio.read_table, which "
        f"drops identifier columns: {bad}"
    )


@pytest.mark.parametrize(
    "snippet",
    [
        # The #68 bug: a picked taught log read as raw text.
        'p = inputs.get("log")\ntext = p.read_text(encoding="utf-8")',
        'p: Path | None = inputs["log"]\nwith open(p) as fh: pass',
        "import csv\nrows = list(csv.reader(fh))",
        "from csv import DictReader",
        "from openpyxl import load_workbook",
        "import openpyxl\nwb = openpyxl.load_workbook(p)",
        "from staffroom.core.csvio import read_csv",
        "from staffroom.core import csvio\nt = csvio.read_xlsx(p)",
        'text = (out / f"{stem}.csv").read_text()',
        'with open(folder / "marks.xlsx", "rb") as fh: pass',
        'data = Path("log.CSV").read_bytes()',
    ],
)
def test_table_read_scan_catches_bypasses(snippet: str) -> None:
    assert table_reads(snippet, {"log"}), snippet


@pytest.mark.parametrize(
    "snippet",
    [
        "from staffroom.core.csvio import read_table\nt = read_table(p)",
        'p = inputs.get("bank")\ntext = p.read_text(encoding="utf-8")',
        'text = Path("bank.md").read_text()',
        'with open("prog.py") as fh: pass',
        'with (out / "x.csv").open("w") as fh: pass',
        'with open(out / "x.csv", mode="w") as fh: pass',
        "import csv\nw = csv.writer(fh)",
        "from openpyxl import Workbook",
    ],
)
def test_table_read_scan_allows_text_and_writes(snippet: str) -> None:
    assert table_reads(snippet, {"log"}) == [], snippet


def test_quiz_taught_log_is_a_table_picker() -> None:
    # The cross-reference above is only as good as this: the taught log is
    # declared as a table input, so a raw read of it would be caught.
    assert "taught_log" in _tool_table_keys()["quiz"]
