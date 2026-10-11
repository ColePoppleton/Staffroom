"""The date in every sheet's header (#107): today for a teacher, a fixed day
when ``STAFFROOM_DATE`` is set, so the docs renders do not change daily."""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

import staffroom.tools as tools_pkg
from staffroom.core.export import DATE_ENV, sheet_date
from staffroom.tools.worksheet.logic import Options, generate
from staffroom.tools.worksheet.sheet import build_document

TOOLS = Path(tools_pkg.__file__).parent


def test_today_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DATE_ENV, raising=False)
    assert sheet_date() == date.today()


def test_blank_counts_as_unset() -> None:
    assert sheet_date({DATE_ENV: "  "}) == date.today()


def test_fixed_date_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATE_ENV, "2026-10-09")
    assert sheet_date() == date(2026, 10, 9)


def test_a_malformed_date_is_refused_not_ignored() -> None:
    with pytest.raises(ValueError, match="STAFFROOM_DATE"):
        sheet_date({DATE_ENV: "9/10/26"})


def test_a_sheet_builder_prints_the_fixed_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(DATE_ENV, "2026-10-09")
    options = Options(topic="binary", seed=1)
    questions = generate(options.topic, options.seed, options.count, options.difficulty)
    doc = build_document(questions, options)
    assert doc.date == date(2026, 10, 9)
    assert "09 October 2026" in doc.header_text
    # An explicit date still wins over the environment.
    assert build_document(questions, options, date(2025, 1, 2)).date == date(2025, 1, 2)


def _calls_date_today(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "today"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in {"date", "datetime"}
        ):
            return True
    return False


def _builds_a_document(tree: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Document"
        for node in ast.walk(tree)
    )


def test_no_sheet_builder_reads_the_clock_itself() -> None:
    """Every module that builds a house-style Document takes its default date
    from sheet_date(), so STAFFROOM_DATE is the one mechanism."""
    offenders = []
    for path in sorted(TOOLS.rglob("*.py")):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if _builds_a_document(tree) and _calls_date_today(tree):
            offenders.append(str(path.relative_to(TOOLS)))
    assert offenders == []
