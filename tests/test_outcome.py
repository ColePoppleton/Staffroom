"""The result strip's words, without a window: chip labels from file names,
the headline split, and RunContext.warn."""

from __future__ import annotations

from pathlib import Path

from staffroom.core.config import load_config
from staffroom.core.outcome import file_chips, split_outcome, warning_count
from staffroom.core.plugin import RunContext

OUT = Path("/out")


def chips(*names: str, labels: dict[Path, str] | None = None) -> list[str]:
    return [f"{c.kind} {c.label}" for c in file_chips([OUT / n for n in names], labels)]


def test_a_sheet_and_its_key() -> None:
    files = ("binary_medium_s42.docx", "binary_medium_s42_key.docx")
    files += ("binary_medium_s42.pdf", "binary_medium_s42_key.pdf")
    # Printable first: the PDFs lead, the tool's order within a kind.
    assert chips(*files) == ["PDF Sheet", "PDF Key", "DOCX Sheet", "DOCX Key"]


def test_files_with_a_shared_prefix_are_named_by_the_rest() -> None:
    marks = ("m_10x_distribution.csv", "m_10x_questions.csv", "m_10x_distribution.png")
    assert chips(*marks) == ["CSV Distribution", "CSV Questions", "PNG Distribution"]
    assert chips(*marks, labels={OUT / "m_10x_distribution.png": "Chart"})[-1] == "PNG Chart"


def test_bugs_variants_and_sheets() -> None:
    names = ("year9_bug1.py", "year9_bug2.py", "year9_bugs.pdf", "year9_bugs_key.pdf")
    assert chips(*names) == ["PDF Sheet", "PDF Key", "PY Bug 1", "PY Bug 2"]


def test_one_file_or_one_name_keeps_its_stem() -> None:
    assert chips("marks_10x_totals.csv") == ["CSV marks_10x_totals"]
    assert chips("bank_kahoot_s1.xlsx", "bank_kahoot_s1.csv") == [
        "XLSX bank_kahoot_s1",
        "CSV bank_kahoot_s1",
    ]
    assert chips() == []


def test_split_outcome() -> None:
    assert split_outcome("10 questions · seed 42") == ("10 questions", "seed 42")
    assert split_outcome("Opened average.py in your editor") == (
        "Opened average.py in your editor",
        "",
    )
    assert warning_count(1) == "1 warning" and warning_count(3) == "3 warnings"


def test_warn_logs_and_tells_the_host(tmp_path: Path) -> None:
    logs: list[str] = []
    warned: list[str] = []
    ctx = RunContext(load_config(), tmp_path, log=logs.append, warned=warned.append)
    ctx.warn("q3 has a mark above its maximum")
    assert logs == ["Warning: q3 has a mark above its maximum"]
    assert warned == ["q3 has a mark above its maximum"]
    RunContext(load_config(), tmp_path).warn("a host with no hook is fine")
