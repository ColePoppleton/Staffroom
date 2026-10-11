"""What the quiz panel finds in its inputs (#17): the bank's summary, its
topics as chips with counts, the running total, the taught log's weeks, the
run button's words; and the panel's inputs folded into the CLI's Options."""

from datetime import date
from pathlib import Path

import pytest

from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.quiz import logic, plugin
from staffroom.tools.quiz.found import (
    as_of_date,
    bank_notes,
    boards_phrase,
    inspect_inputs,
    taught_notes,
    topic_chips,
    topics_total,
)
from staffroom.tools.quiz.logic import Options
from staffroom.tools.quiz.panel import options_from

EXAMPLES = Path(__file__).resolve().parents[5] / "examples"
BANK = EXAMPLES / "question_bank.md"


@pytest.fixture
def bank() -> logic.Bank:
    return logic.parse_bank(BANK.read_text())


def test_the_bank_summary_reads_as_one_line(bank: logic.Bank) -> None:
    notes = bank_notes(bank)
    assert [(n.text, n.ok) for n in notes] == [
        ("13 questions · 6 topics · OCR and AQA spec points · no problems", True)
    ]
    ocr_only = logic.parse_bank("## Q\ntags: ocr:1.1.1, topic:cpu\nanswer: x\n")
    assert boards_phrase(ocr_only) == "OCR spec points"
    assert boards_phrase(logic.parse_bank("## Q\nanswer: x\n")) == "no spec points"


def test_problems_show_the_first_with_its_line_and_unknown_spec_tags() -> None:
    text = "## A\ntype: tf\nanswer: maybe\n## B\ntype: tf\nanswer: nope\n## C\n"
    text += "tags: ocr:9.9.9, topic:x\nanswer: 1\n"
    notes = bank_notes(logic.parse_bank(text))
    assert notes[0].text == "1 question · 1 topic · OCR spec points · 3 problems"
    assert not notes[0].ok
    assert notes[1].text.startswith("Line 1") and "(and 1 more" in notes[1].text
    assert notes[2].text == "Not in the spec: ocr:9.9.9"
    empty = bank_notes(logic.parse_bank("# just a title\n"))
    assert len(empty) == 1 and "No questions found" in empty[0].text


def test_topic_chips_count_questions_in_bank_order(bank: logic.Bank) -> None:
    chips = topic_chips(bank)
    assert [c.value for c in chips] == bank.topics
    assert sum(c.count or 0 for c in chips) == len(bank.questions)  # one topic each here
    assert {c.value: c.count for c in chips}["binary"] == 4


def test_the_running_total_follows_the_chips_the_spec_and_the_count(bank: logic.Bank) -> None:
    def total(**kw: object) -> str:
        return topics_total(bank, Options(**kw)).text  # type: ignore[arg-type]

    assert total() == "No topic picked: any of the 13 questions · 10 of them picked"
    assert total(topics="binary,cpu,loops") == "8 questions in the chosen topics · all 8 picked"
    assert total(topics="binary", count=3) == "4 questions in the chosen topics · 3 of them picked"
    assert total(topics="searching") == "1 question in the chosen topics"
    assert "with spec ocr:1.2" in total(spec="ocr:1.2")
    assert not topics_total(bank, Options(topics="nothing-here")).ok


def test_the_taught_weeks_and_what_they_leave(bank: logic.Bank) -> None:
    log = [
        logic.TaughtEntry(date(2026, 10, 1), "networks"),
        logic.TaughtEntry(date(2026, 9, 17), "loops"),
        logic.TaughtEntry(date(2026, 9, 17), "recursion"),
    ]
    notes = taught_notes(bank, log, date(2026, 10, 8), Options())
    assert notes[0].text == (
        "1 week before Thu 8 Oct: networks · 3 weeks: loops, recursion · 6 weeks: nothing"
    )
    assert notes[1].text == "4 questions in those topics · all 4 picked"
    assert notes[2].text == "Not in the bank: recursion" and not notes[2].ok
    nothing = taught_notes(bank, [], date(2026, 10, 8), Options())
    assert nothing[-1].text == "Nothing in the log falls in those weeks."


def test_the_as_of_date() -> None:
    assert as_of_date("", date(2026, 10, 9)) == date(2026, 10, 9)
    assert as_of_date(" 2026-10-08 ") == date(2026, 10, 8)
    with pytest.raises(ToolError, match="YYYY-MM-DD"):
        as_of_date("8/10/26")


def test_the_panels_inputs_fold_into_the_clis_options() -> None:
    assert Options().fmt == "donow"  # the do-now first until #1 records a Kahoot import
    base = Options(count=8, seed=3, spec="ocr:1.2", title="Starter")
    folded = options_from(
        {"options": base, "fmt": "forms", "pick": "taught", "topics": ("cpu",), "as_of": "x"}
    )
    assert folded == Options(
        fmt="forms",
        count=8,
        seed=3,
        topics="cpu",
        spec="ocr:1.2",
        retrieval=True,
        today="x",
        title="Starter",
    )
    assert options_from({"options": base}) == base  # the CLI's inputs are untouched
    assert options_from({"pick": "topics", "topics": ()}).topics == ""


def test_inspect_names_the_button_and_fills_the_chips() -> None:
    inspection = inspect_inputs({"source": BANK, "fmt": "kahoot", "topics": ("cpu",)})
    assert inspection.run_label == "Make Kahoot"
    assert inspection.found["source"].rows is not None
    assert inspection.found["source"].rows_label == "Preview questions"
    topics = inspection.found["topics"]
    assert topics.chips is not None and len(topics.chips) == 6
    assert topics.notes[0].text == "2 questions in the chosen topics · all 2 picked"
    no_bank = inspect_inputs({})
    assert no_bank.found["topics"].chips == () and "source" not in no_bank.found
    missing = inspect_inputs({"source": EXAMPLES / "no_such_bank.md"})
    assert "Could not read" in missing.found["source"].notes[0].text


def test_a_panel_run_matches_the_same_cli_options(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    panel_inputs = {
        "source": BANK,
        "fmt": "forms",
        "pick": "topics",
        "topics": ("binary",),
        "as_of": "",
        "options": Options(count=3, seed=2),
    }
    from_panel = plugin.run(panel_inputs, ctx)
    cli = Options(fmt="forms", count=3, seed=2, topics="binary")
    from_cli = plugin.run({"source": BANK, "options": cli}, ctx)
    assert from_panel.texts["paste"] == from_cli.texts["paste"]
    assert [f.name for f in from_panel.files] == ["question_bank_forms_s2.txt"]
    assert from_panel.outcome == "3 questions · Forms · binary · seed 2"
    assert from_panel.tables["questions"].columns == ["#", "Question", "Topic · type"]
    first = from_panel.tables["chosen"].rows[0][2]
    assert from_panel.tables["questions"].rows[0] == [1, first, "binary · short"]
