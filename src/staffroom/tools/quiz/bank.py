"""Reading quiz's two files: the question bank (Markdown) and the taught log
(a date,topic table, always through :func:`staffroom.core.csvio.read_table`
so a column that could name a pupil is dropped before quiz sees it). The
parsing itself is :mod:`staffroom.tools.quiz.logic`; this module only reads."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from staffroom.core.csvio import read_table
from staffroom.core.plugin import ToolError
from staffroom.core.table import Table
from staffroom.tools.quiz import logic

NO_QUESTIONS = (
    "No questions found. Each question starts with '## ' (see examples/question_bank.md)."
)


def read_bank_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"Could not read {path}: {exc}") from exc
    except UnicodeDecodeError:
        raise ToolError(f"{path.name} is not a text file.") from None


def load_bank(path: Path) -> logic.Bank:
    """The bank at ``path``; a ToolError when it cannot be read or holds no
    questions."""
    bank = logic.parse_bank(read_bank_text(path))
    if not bank.questions:
        raise ToolError(NO_QUESTIONS)
    return bank


@lru_cache(maxsize=8)
def _parsed(path: str, _mtime_ns: int, _size: int) -> logic.Bank:
    return logic.parse_bank(read_bank_text(Path(path)))


def peek_bank(path: Path) -> logic.Bank:
    """The bank, parsed once per version of the file: the panel asks on every
    chip toggled. Raises ToolError like :func:`read_bank_text`."""
    try:
        stat = path.stat()
    except OSError as exc:
        raise ToolError(f"Could not read {path}: {exc.strerror or exc}") from exc
    return _parsed(str(path), stat.st_mtime_ns, stat.st_size)


def load_taught_log(path: Path) -> Table:
    """The taught log as a table, through :func:`staffroom.core.csvio.read_table`
    like every other table: a column that could identify a pupil (a name, a
    class) is dropped there, before this tool sees it; ``dropped_columns``
    names it by its header only. Missing, unreadable or wrong-kind files are
    ToolErrors."""
    return read_table(path)
