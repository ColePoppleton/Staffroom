"""Bank parsing, exporters, and the acceptance for the retrieval scheduler:
it picks only from topics taught in the configured windows."""

import csv
import io
from datetime import date
from pathlib import Path

import pytest
from openpyxl import load_workbook
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext
from staffroom.tools.quiz import logic, plugin
from staffroom.tools.quiz.export import write_kahoot
from staffroom.tools.quiz.logic import KAHOOT_HEADERS, Options

runner = CliRunner()
EXAMPLES = Path(__file__).resolve().parents[5] / "examples"


@pytest.fixture
def bank() -> logic.Bank:
    return logic.parse_bank((EXAMPLES / "question_bank.md").read_text())


def test_parse_example_bank(bank: logic.Bank) -> None:
    assert bank.errors == []
    assert len(bank.questions) == 13
    q = bank.questions[0]
    assert q.qtype == "mcq" and q.correct == (0,) and q.options[0] == "Central Processing Unit"
    assert q.tags == ("ocr:1.1.1", "aqa:3.4.4", "topic:cpu") and q.topics == ("cpu",)
    assert q.why.startswith("The CPU")
    tf = bank.questions[2]
    assert tf.qtype == "tf" and tf.options == ("True", "False") and tf.correct == (0,)
    short = bank.questions[4]
    assert short.qtype == "short" and short.answer == "10"
    assert bank.topics == ["cpu", "memory", "binary", "loops", "searching", "networks"]


def test_parse_errors_have_line_numbers() -> None:
    text = (
        "stray line\n## No options\ntype: mcq\n## Bad tf\ntype: tf\nanswer: maybe\n"
        "## Fine\nanswer: 4\n"
    )
    b = logic.parse_bank(text)
    assert [q.text for q in b.questions] == ["Fine"]
    assert any("line 1" in e for e in b.errors)
    assert any("line 2" in e and "two" in e for e in b.errors)
    assert any("line 4" in e and "true" in e for e in b.errors)


def test_filters_and_choose(bank: logic.Bank) -> None:
    binary = logic.filter_questions(bank.questions, topics="binary")
    assert {q.number for q in binary} == {5, 6, 7, 8}
    memory_unit = logic.filter_questions(bank.questions, spec="ocr:1.2")
    assert {q.number for q in memory_unit} == {3, 4, 5, 6, 7, 8}
    assert logic.filter_questions(bank.questions, spec="aqa:3.3.2") == binary[:3]
    chosen = logic.choose(bank.questions, 5, seed=3)
    assert len(chosen) == 5 and chosen == sorted(chosen, key=lambda q: q.number)
    assert logic.choose(bank.questions, 5, seed=3) == chosen


def test_retrieval_picks_only_from_taught_windows(bank: logic.Bank) -> None:
    entries, errors = logic.parse_taught_log((EXAMPLES / "taught_log.csv").read_text())
    assert errors == [] and len(entries) == 6
    today = date(2026, 10, 8)
    windows = logic.topics_in_windows(entries, today)
    assert windows == {1: ["networks"], 3: ["loops"], 6: ["cpu"]}
    chosen, _ = logic.retrieval_pick(bank.questions, entries, today, 10, seed=1)
    assert chosen
    assert all(set(q.topics) & {"networks", "loops", "cpu"} for q in chosen)
    assert not any("memory" in q.topics or "binary" in q.topics for q in chosen)
    assert {q.topics[0] for q in chosen} == {"networks", "loops", "cpu"}
    # A date with nothing taught in any window picks nothing.
    none, w = logic.retrieval_pick(bank.questions, entries, date(2027, 1, 1), 10, seed=1)
    assert none == [] and all(v == [] for v in w.values())
    bad, errs = logic.parse_taught_log("date,topic\nnot-a-date,cpu\n2026-01-01,\n")
    assert bad == [] and len(errs) == 2
    assert logic.parse_taught_log("x,y\n1,2\n")[1] == [
        "taught log needs 'date' and 'topic' columns"
    ]


def test_kahoot_rows_and_files(bank: logic.Bank, tmp_path: Path) -> None:
    notes: list[str] = []
    rows = logic.kahoot_rows(bank.questions, notes)
    assert all(len(r) == 7 for r in rows)
    assert rows[0][0] == "What does CPU stand for?" and rows[0][6] == "1" and rows[0][5] == "20"
    tf = next(r for r in rows if r[0] == "RAM is volatile.")
    assert tf[1:5] == ["True", "False", "", ""] and tf[6] == "1"
    short = next(r for r in rows if r[0] == "What is 1010 in denary?")
    assert "10" in short[1:5] and short[6] == str(short[1:5].index("10") + 1)
    smtp = next(r for r in rows if r[0].startswith("Name the protocol"))
    assert "SMTP" in smtp[1:5] and all(smtp[1:5])  # distractors borrowed from other short answers
    assert all(int(r[5]) in logic.KAHOOT_TIMES for r in rows)

    files = write_kahoot(bank.questions, tmp_path, "bank", notes)
    assert [f.name for f in files] == ["bank_kahoot.xlsx", "bank_kahoot.csv"]
    ws = load_workbook(files[0]).active
    assert ws is not None
    headers = [ws.cell(row=8, column=c).value for c in range(2, 9)]
    assert tuple(headers) == KAHOOT_HEADERS
    assert ws.cell(row=9, column=1).value == 1 and ws.cell(row=9, column=2).value == rows[0][0]
    assert ws.cell(row=9, column=7).value == 20
    reader = csv.reader(io.StringIO(files[1].read_text().split("\n", 1)[1]))
    assert tuple(next(reader)) == KAHOOT_HEADERS


def test_clipping_and_time_snapping() -> None:
    long = logic.Question(1, "x" * 130, "mcq", ("a" * 80, "b"), (0,), "", (), 25)
    notes: list[str] = []
    rows = logic.kahoot_rows([long], notes)
    assert len(rows[0][0]) == 120 and len(rows[0][1]) == 75 and rows[0][5] == "20"
    assert len(notes) == 2


def test_forms_text_and_donow(bank: logic.Bank, tmp_path: Path) -> None:
    text = logic.forms_text(bank.questions[:3], "Quick quiz")
    assert text.startswith(
        "Quick quiz\n\n1. What does CPU stand for?\n   A) Central Processing Unit"
    )
    assert "Answers\n\n1. A\n2. B\n3. A\n" in text
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    result = plugin.run(
        {
            "source": EXAMPLES / "question_bank.md",
            "options": Options(fmt="donow", count=4, seed=2, title="Do now"),
        },
        ctx,
    )
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "question_bank_donow.docx",
        "question_bank_donow.pdf",
        "question_bank_donow_key.docx",
        "question_bank_donow_key.pdf",
    ]
    assert "ANSWER KEY" in result.texts["preview"] and result.tables["chosen"].shape[0] == 4


def test_plugin_retrieval_and_cli(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    options = Options(fmt="forms", retrieval=True, today="2026-10-08", count=6, seed=1)
    result = plugin.run(
        {
            "source": EXAMPLES / "question_bank.md",
            "taught_log": EXAMPLES / "taught_log.csv",
            "options": options,
        },
        ctx,
    )
    topics = {str(row[3]) for row in result.tables["chosen"].rows}
    assert topics <= {"networks", "loops", "cpu"}
    r = runner.invoke(
        app,
        [
            "quiz",
            "export",
            "--bank",
            str(EXAMPLES / "question_bank.md"),
            "-f",
            "kahoot",
            "-t",
            "binary",
            "-n",
            "3",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert (tmp_path / "question_bank_kahoot.xlsx").exists()
    r = runner.invoke(app, ["quiz", "list", "--bank", str(EXAMPLES / "question_bank.md")])
    assert r.exit_code == 0 and "13 questions" in r.output
    r = runner.invoke(app, ["quiz", "check", "--bank", str(EXAMPLES / "question_bank.md")])
    assert r.exit_code == 0 and "0 problems" in r.output and "0 unknown spec tags" in r.output
    r = runner.invoke(app, ["quiz", "spec", "aqa"])
    assert r.exit_code == 0 and "aqa:3.3.4" in r.output
    r = runner.invoke(
        app,
        [
            "quiz",
            "retrieval",
            "--bank",
            str(EXAMPLES / "question_bank.md"),
            "--log",
            str(EXAMPLES / "taught_log.csv"),
            "--date",
            "2026-10-08",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert "networks" in r.output or "loops" in r.output
