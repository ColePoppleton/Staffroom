"""Root conftest: shared fixtures for tests/ and every tool's tests/. Every test
gets an isolated config/log home so nothing touches ~/.config/teaching-tools."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from teaching_tools.core import paths

EXAMPLES = paths.examples_dir()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    home = tmp_path / "tt-home"
    monkeypatch.setenv("TEACHING_TOOLS_HOME", str(home))
    yield home


@pytest.fixture
def example_class_list() -> Path:
    return EXAMPLES / "class_list.csv"


@pytest.fixture
def example_marks() -> Path:
    return EXAMPLES / "marks_10x.csv"


@pytest.fixture(scope="session", autouse=True)
def _offscreen_qt() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
