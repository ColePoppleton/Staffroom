"""The installed copy's command line reads well for a teacher (#20): only the
``staff`` and ``staffroom`` commands, help text as sentences with an example,
the quiz bank as an argument, and log records on the terminal only with -v."""

from __future__ import annotations

import inspect
import re
import shlex
import tomllib
from collections.abc import Iterator
from pathlib import Path

import click
import pytest
import typer
from typer.testing import CliRunner

from staffroom.cli import app, tidy_help
from staffroom.core import paths

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = paths.examples_dir()
runner = CliRunner()

# Commands whose help still lacks an Example: paragraph, because a parallel
# change owns their file (#46). Remove a name when its example lands.
EXAMPLE_PENDING = {"staff new", "staff parsons make", "staff trace make"}

# The old command names as a word: not `tt-body` (a PDF style) or `.tt` (CSS).
OLD_NAMES = re.compile(r"(?<![\w.$/-])tt(?:-gui)?(?![\w-])")


def _commands() -> Iterator[tuple[str, click.Command]]:
    def walk(cmd: click.Command, path: str) -> Iterator[tuple[str, click.Command]]:
        subcommands = getattr(cmd, "commands", None)  # typer's groups are not click.Group
        if subcommands is not None:
            for name, sub in sorted(subcommands.items()):
                yield from walk(sub, f"{path} {name}")
        else:
            yield path, cmd

    yield from walk(typer.main.get_command(app), "staff")


def _example(help_text: str) -> str | None:
    for paragraph in help_text.split("\n\n"):
        if paragraph.startswith("Example: "):
            return paragraph.removeprefix("Example: ")
    return None


def test_only_staff_and_staffroom_are_installed() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["scripts"] == {
        "staff": "staffroom.cli:main",
        "staffroom": "staffroom.shell.app:main",
    }


def test_nothing_outside_the_changelog_and_audits_calls_the_old_names() -> None:
    files = [ROOT / name for name in ("README.md", "CLAUDE.md", "justfile", "mkdocs.yml")]
    for folder in ("docs", "scripts", ".github", "packaging"):
        files += [p for p in (ROOT / folder).rglob("*") if p.is_file()]
    hits = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        # Audits are dated records of what was run then; the changelog is history.
        if rel.startswith("docs/audits/") or rel == "docs/changelog.md":
            continue
        if path.suffix in {".png", ".pdf", ".icns", ".ttf", ".otf", ".woff2", ".ico"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits += [f"{rel}: {line.strip()}" for line in text.splitlines() if OLD_NAMES.search(line)]
    assert hits == []


def test_tidy_help_joins_wrapped_lines_and_drops_rst_quoting() -> None:
    text = """Compare this copy with ``origin/main``
    then update.

    Example: staff update --check
    """
    assert tidy_help(text) == (
        "Compare this copy with origin/main then update.\n\nExample: staff update --check"
    )
    assert tidy_help("Keep:\n\n\bline one\nline two") == "Keep:\n\n\bline one\nline two"


@pytest.mark.parametrize(("path", "cmd"), list(_commands()), ids=lambda v: str(v))
def test_help_reads_as_sentences_with_an_example(path: str, cmd: click.Command) -> None:
    text = inspect.cleandoc(cmd.help or "")
    assert text, f"{path} has no help"
    assert "``" not in text, f"{path}: reStructuredText quoting in help"
    for paragraph in text.split("\n\n"):
        assert "\n" not in paragraph, f"{path}: a hard line break in {paragraph!r}"
    example = _example(text)
    if path in EXAMPLE_PENDING:
        return
    assert example is not None, f"{path}: no 'Example: staff …' paragraph"
    assert example.startswith(path + " ") or example == path, f"{path}: example runs {example}"
    words = shlex.split(example)
    known = {opt for p in cmd.params for opt in (*p.opts, *p.secondary_opts)}
    flags = [w for w in words if w.startswith("-")]
    assert set(flags) <= known, f"{path}: example uses unknown options {set(flags) - known}"


def test_root_help_lists_one_line_per_command() -> None:
    result = runner.invoke(app, ["--help"], terminal_width=200)
    assert result.exit_code == 0, result.output
    assert "``" not in result.output
    assert "Update this copy of Staffroom to the latest release." in result.output
    assert "Show which tools you have used, how often, and when last." in result.output
    assert "staff COMMAND --help" in result.output


# ---------------------------------------------------------------- quiz bank argument
BANK = str(EXAMPLES / "question_bank.md")


@pytest.mark.parametrize("args", [[BANK], ["--bank", BANK], ["-b", BANK], [BANK, "-b", BANK]])
def test_quiz_check_takes_the_bank_as_an_argument_or_the_old_flag(args: list[str]) -> None:
    result = runner.invoke(app, ["quiz", "check", *args])
    assert result.exit_code == 0, result.output
    assert "13 questions, 0 problems" in result.output


def test_quiz_export_and_retrieval_take_the_bank_as_an_argument(tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["quiz", "export", BANK, "--format", "donow", "--n", "3", "--out", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    log = str(EXAMPLES / "taught_log.csv")
    result = runner.invoke(
        app,
        ["quiz", "retrieval", BANK, "--log", log, "--date", "2026-10-08", "--out", str(tmp_path)],
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["quiz", "list", BANK])
    assert result.exit_code == 0 and "13 questions" in result.output


def _flat(output: str) -> str:
    """Error text with rich's box and its line wrapping taken out."""
    return re.sub(r"[│╭╮╰╯─\s]+", " ", output)


def test_quiz_without_a_bank_says_what_to_give() -> None:
    result = runner.invoke(app, ["quiz", "check"])
    assert result.exit_code == 2
    assert "give the question bank file, e.g. examples/question_bank.md" in _flat(result.output)
    assert "Missing option" not in result.output


def test_quiz_refuses_two_different_banks(tmp_path: Path) -> None:
    other = tmp_path / "other.md"
    other.write_text("## What is a bit?\ntype: short\nanswer: a binary digit\n", encoding="utf-8")
    result = runner.invoke(app, ["quiz", "check", BANK, "--bank", str(other)])
    assert result.exit_code == 2
    assert "two different banks" in _flat(result.output)


# ---------------------------------------------------------------- quiet by default
LOG_RECORD = re.compile(r"^\d\d:\d\d:\d\d (INFO|WARNING|DEBUG)\s", re.M)


def _marks_with_an_id_column(tmp_path: Path) -> list[str]:
    # FAKE DATA: an opaque row number column, which marks drops and says so.
    source = tmp_path / "rows.csv"
    source.write_text("# FAKE DATA\nid,q1,q2\n1,3,4\n2,2,5\n", encoding="utf-8")
    return ["marks", "run", str(source), "--max", "5,5", "--out", str(tmp_path / "out")]


def test_cli_prints_no_log_records_without_verbose(tmp_path: Path, isolated_home: Path) -> None:
    result = runner.invoke(app, _marks_with_an_id_column(tmp_path))
    assert result.exit_code == 0, result.output
    assert "Dropped identifier column(s), never used: id" in result.output  # the friendly line
    assert not LOG_RECORD.search(result.output), result.output
    # The record still goes to the log file, for a bug report.
    log_text = (isolated_home / "logs" / "staffroom.log").read_text(encoding="utf-8")
    assert "dropped identifier column(s) id" in log_text


def test_verbose_prints_the_log_records(tmp_path: Path) -> None:
    result = runner.invoke(app, ["-v", *_marks_with_an_id_column(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "Dropped identifier column(s), never used: id" in result.output
    assert LOG_RECORD.search(result.output), result.output
