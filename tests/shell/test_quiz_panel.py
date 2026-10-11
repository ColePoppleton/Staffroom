"""Quiz starts from the bank (#17): the bank as a chip with what was found in
it, *Make* with the do-now first, *Questions from* the bank's own topics as
chips (or what was taught 1, 3 and 6 weeks ago), and the do-now page as the
main output."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.library.service import LibraryService
from staffroom.core.paths import examples_dir
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel

BANK = examples_dir() / "question_bank.md"
LOG = examples_dir() / "taught_log.csv"


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    return win


def _quiz(window: MainWindow) -> ToolPanel:
    window.sidebar.select("quiz")
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel)
    return panel


def _run(panel: ToolPanel, qtbot: QtBot) -> None:
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as blocker:
        panel.start_run()
    assert blocker.args == [True], panel.strip.text()


def _visible_tabs(panel: ToolPanel) -> list[str]:
    tabs = panel.results.tabs
    assert tabs is not None
    return [tabs.tabText(i) for i in range(tabs.count()) if tabs.isTabVisible(i)]


# -- the bank ---------------------------------------------------------------
def test_the_bank_is_a_chip_with_what_was_found_in_it(window: MainWindow) -> None:
    panel = _quiz(window)
    picker = panel.resource_pickers["source"]
    assert picker.chip is not None and picker.edit.isHidden()
    assert picker.folder.text() == "No file yet"
    assert not panel.found["source"].isVisibleTo(panel)
    panel.set_input_path("source", BANK)
    assert picker.name.text() == "question_bank.md" and picker.badge.text() == "MD"
    assert picker.chip.toolTip() == str(BANK)
    found = panel.found["source"]
    assert [n.text for n in found.notes()] == [
        "13 questions · 6 topics · OCR and AQA spec points · no problems"
    ]
    assert found.preview_button.isVisibleTo(panel)
    assert found.preview_button.text() == "Preview questions"
    found.preview_button.click()
    assert found.dialog is not None
    found.dialog.close()


def test_a_bank_with_a_problem_names_its_first_line(window: MainWindow, tmp_path: Path) -> None:
    bank = tmp_path / "broken.md"
    bank.write_text(
        "## What is 2 + 2?\ntype: short\ntags: topic:sums\nanswer: 4\n\n"
        "## Pick one\ntype: mcqq\ntags: topic:sums\n- [x] A\n- [ ] B\n",
        encoding="utf-8",
    )
    panel = _quiz(window)
    panel.set_input_path("source", bank)
    notes = panel.found["source"].notes()
    assert notes[0].text.startswith("1 question · 1 topic") and not notes[0].ok
    assert notes[1].text.startswith("Line 6: type must be") and not notes[1].ok


# -- make -------------------------------------------------------------------
def test_do_now_is_the_default_and_the_button_says_what_it_makes(window: MainWindow) -> None:
    panel = _quiz(window)
    make = panel.choices["fmt"]
    assert list(make.buttons) == ["donow", "kahoot", "forms"]
    assert make.value() == "donow"
    assert panel.run_bar.button.text() == "Make do-now"
    make.set_value("kahoot")
    assert panel.run_bar.button.text() == "Make Kahoot"
    make.set_value("forms")
    assert panel.run_bar.button.text() == "Make Forms text"


# -- questions from ---------------------------------------------------------
def test_the_banks_topics_are_chips_with_counts_and_a_running_total(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    panel = _quiz(window)
    chips = panel.chip_choices["topics"]
    assert not chips.chips and chips.empty.isVisibleTo(panel)  # no bank yet
    panel.set_input_path("source", BANK)
    assert [(c.option.value, c.option.count) for c in chips.chips.values()] == [
        ("cpu", 2),
        ("memory", 2),
        ("binary", 4),
        ("loops", 2),
        ("searching", 1),
        ("networks", 2),
    ]
    assert chips.notes() == ["No topic picked: any of the 13 questions · 10 of them picked"]
    for topic in ("binary", "cpu", "loops"):
        chips.chips[topic].click()
    assert chips.value() == ("cpu", "binary", "loops")
    assert chips.chips["binary"].property("on") == "true"
    assert chips.notes() == ["8 questions in the chosen topics · all 8 picked"]
    assert panel.collect_inputs()["topics"] == ("cpu", "binary", "loops")

    _run(panel, qtbot)
    listed = panel.results.tables["questions"][0]
    assert listed.rowCount() == 8
    assert panel.strip.text().startswith("8 questions · cpu, binary, loops · seed 1")
    assert (tmp_path / "out" / "question_bank_donow_s1.pdf").exists()


def test_a_new_bank_keeps_the_chips_it_still_has(window: MainWindow, tmp_path: Path) -> None:
    panel = _quiz(window)
    panel.set_input_path("source", BANK)
    chips = panel.chip_choices["topics"]
    chips.set_value(["binary", "memory"])
    other = tmp_path / "other.md"
    other.write_text(
        "## What is 1 + 1 in binary?\ntype: short\ntags: topic:binary\nanswer: 10\n",
        encoding="utf-8",
    )
    panel.set_input_path("source", other)
    assert list(chips.chips) == ["binary"]
    assert chips.value() == ("binary",)
    assert chips.notes() == ["1 question in the chosen topics"]


def test_taught_shows_the_log_and_the_date_only_for_retrieval(window: MainWindow) -> None:
    """Retrieval is a source of questions, not a tick box: the chips give way
    to the taught log and the date, which hide (with no hairline) otherwise."""
    panel = _quiz(window)
    source = panel.choices["pick"]
    assert source.value() == "topics"
    assert panel.hidden_inputs() == {"taught_log", "as_of"}
    assert panel.groups["topics"].isVisibleTo(panel)
    assert "topics" not in panel.dividers and "taught_log" not in panel.dividers  # joined
    source.set_value("taught")
    assert panel.hidden_inputs() == {"topics"}
    assert panel.groups["taught_log"].isVisibleTo(panel)
    assert panel.groups["as_of"].isVisibleTo(panel)
    assert not panel.groups["topics"].isVisibleTo(panel)


def test_a_hidden_taught_log_is_not_handed_to_the_tool(window: MainWindow) -> None:
    panel = _quiz(window)
    source = panel.choices["pick"]
    source.set_value("taught")
    panel.set_input_path("taught_log", LOG)
    assert panel.collect_inputs()["taught_log"] == LOG
    source.set_value("topics")
    assert panel.collect_inputs()["taught_log"] is None
    assert panel.pickers["taught_log"].value() == LOG  # kept for when it comes back
    source.set_value("taught")
    assert panel.collect_inputs()["taught_log"] == LOG


def test_taught_asks_for_the_log_says_what_it_found_and_runs(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    panel = _quiz(window)
    panel.set_input_path("source", BANK)
    assert panel.missing_inputs(panel.collect_inputs()) == []
    panel.choices["pick"].set_value("taught")
    panel.start_run()
    assert "Fill in: Taught log" in panel.strip.text()
    panel.set_input_path("taught_log", LOG)
    panel.set_text("as_of", "2026-10-08")
    notes = [n.text for n in panel.found["taught_log"].notes()]
    assert notes[0] == "1 week before Thu 8 Oct: networks · 3 weeks: loops · 6 weeks: cpu"
    assert notes[1] == "6 questions in those topics · all 6 picked"
    _run(panel, qtbot)
    assert (tmp_path / "out" / "question_bank_retrieval_2026-10-08_donow_s1.pdf").exists()


def test_the_taught_log_drops_a_column_that_could_name_a_pupil(
    window: MainWindow, tmp_path: Path
) -> None:
    log = tmp_path / "log.csv"
    log.write_text("date,topic,Class\n2026-10-01,binary,10X\n", encoding="utf-8")
    panel = _quiz(window)
    panel.set_input_path("source", BANK)
    panel.choices["pick"].set_value("taught")
    panel.set_input_path("taught_log", log)
    notes = panel.found["taught_log"].notes()
    assert notes[0].text == "Never read: Class (could name a pupil)" and not notes[0].ok
    assert all("10X" not in n.text for n in notes)


# -- count, seed, more ------------------------------------------------------
def test_count_and_seed_share_a_row_and_spec_points_wait_under_more(
    window: MainWindow,
) -> None:
    panel = _quiz(window)
    form = panel.forms["options"]
    assert form.inline_row is not None
    assert form.widgets["seed"].parent() is form.inline_row
    assert form.more_button is not None and not form.more_open()
    assert {"spec", "title"}.isdisjoint(form.shown_fields())
    form.more_button.click()
    assert {"spec", "title"} <= set(form.shown_fields())
    form.more_button.click()
    assert {"spec", "title"}.isdisjoint(form.shown_fields())
    form.set_field("spec", "ocr:1.2")  # a value that steers the run never hides
    assert form.more_open() and "spec" in form.shown_fields()
    panel.set_input_path("source", BANK)
    total = panel.chip_choices["topics"].notes()
    assert total[0].startswith("No topic picked: any of the ") and "with spec ocr:1.2" in total[0]


# -- the output -------------------------------------------------------------
def test_do_now_pages_come_first_and_kahoot_shows_its_paste_text(
    window: MainWindow, qtbot: QtBot
) -> None:
    panel = _quiz(window)
    panel.set_input_path("source", BANK)
    assert _visible_tabs(panel) == ["Sheet", "Key", "Chosen questions"]  # Paste text waits
    _run(panel, qtbot)
    preview = panel.results.page_previews["pages"]
    assert preview.page_count("sheet") >= 1 and preview.page_count("key") >= 1
    assert _visible_tabs(panel)[2] == "Chosen questions"
    tabs = panel.results.tabs
    assert tabs is not None and tabs.tabText(tabs.currentIndex()).startswith("Sheet")
    panel.choices["fmt"].set_value("kahoot")
    _run(panel, qtbot)
    assert _visible_tabs(panel) == ["Chosen questions", "Paste text"]
    assert "Question - max 120" in panel.results.text_views["paste"].toPlainText()
    assert panel.results.tables["questions"][0].rowCount() == 10


# -- from the Library -------------------------------------------------------
def test_from_a_bank_in_the_library_to_a_do_now_in_four_actions(
    qtbot: QtBot, resources_root: Path, tmp_path: Path
) -> None:
    """The acceptance count for #17: select the bank, Quiz, one topic chip,
    Make do-now; the sheet is then on screen with Print… under it."""
    shutil.copy(BANK, resources_root / "Python" / "question_bank.md")
    service = LibraryService(resources_root, tmp_path / "library.db", opener=lambda _a: None)
    service.index()
    config = load_config()
    config.general.resources_root = str(resources_root)
    config.general.output_dir = str(tmp_path / "out")
    window = MainWindow(config, library=service, auto_index=False)
    qtbot.addWidget(window)
    window.show()

    window.show_library()
    window.resources.select("Python/question_bank.md")  # 1
    window.use_bar.buttons["quiz"].click()  # 2
    panel = window.panel_for("quiz")
    assert window.stack.currentWidget() is panel
    assert panel.resource_pickers["source"].folder.text() == "Python"
    panel.chip_choices["topics"].chips["binary"].click()  # 3
    with qtbot.waitSignal(panel.run_finished, timeout=20000) as blocker:
        panel.run_bar.button.click()  # 4: Make do-now
    assert blocker.args == [True], panel.strip.text()
    assert panel.results.page_previews["pages"].page_count("sheet") >= 1
    tabs = panel.results.tabs
    assert tabs is not None and tabs.tabText(tabs.currentIndex()).startswith("Sheet")
    assert (tmp_path / "out" / "question_bank_donow_s1.pdf").exists()
