"""The result strip (#84): one outcome line, the files as buttons, warnings as
a count, the run log behind Details. No Log card in any panel."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QLabel
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.outcome import file_chips
from staffroom.core.plugin import RunResult, ToolError
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets import output_pane
from staffroom.shell.widgets.elided_label import ElidedLabel
from staffroom.shell.widgets.result_strip import (
    FAILURE_LINES,
    IDLE_TEXT,
    MAX_CHIPS,
    ResultStrip,
)


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    monkeypatch.setattr(output_pane, "_details_open", {})  # a fresh "session"
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    config.general.sessions_root = str(tmp_path / "sessions")
    win = MainWindow(config, auto_index=False, first_run=False)
    qtbot.addWidget(win)
    win.resize(1240, 780)
    win.show()
    return win


@pytest.fixture
def narrow_window(window: MainWindow) -> MainWindow:
    """The launcher at its minimum size (``MainWindow.setMinimumSize``)."""
    window.resize(window.minimumSize())
    QApplication.processEvents()
    assert window.width() == 1040
    return window


def open_tool(window: MainWindow, name: str) -> ToolPanel:
    window.go_to_tool(name)
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == name
    QApplication.processEvents()
    return panel


def run(panel: ToolPanel, qtbot: QtBot, *, ok: bool = True) -> None:
    with qtbot.waitSignal(panel.run_finished, timeout=60000) as blocker:
        panel.start_run()
    assert blocker.args == [ok], panel.strip.text()
    QApplication.processEvents()


def test_every_panel_has_the_strip_and_no_log_card(window: MainWindow) -> None:
    for plugin in window.visible_plugins:
        panel = open_tool(window, plugin.name)
        assert panel.results.strip_slot.itemAt(0).widget() is panel.strip
        assert panel.strip.text() == IDLE_TEXT, plugin.name
        assert panel.strip.folder_chip.isVisibleTo(panel), plugin.name
        assert not panel.strip.chips
        # The log is behind Details, closed; no "Log" heading anywhere.
        assert not panel.results.details_open
        assert not panel.results.log_view.isVisibleTo(panel)
        headings = [w.text() for w in panel.results.findChildren(QLabel) if w.isVisibleTo(panel)]
        assert "LOG" not in headings and "Log" not in headings, plugin.name
        # The foot is the button and where it writes: no status line.
        assert not hasattr(panel.run_bar, "status")


def test_chips_match_the_files_written(
    window: MainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel = open_tool(window, "worksheet")
    run(panel, qtbot)
    result = panel.last_result
    assert result is not None and len(result.files) == 4
    assert panel.strip.state == "success"
    assert panel.strip.text() == result.outcome
    assert panel.strip.headline.text() == "10 questions"
    assert {c.path for c in panel.strip.files} == set(result.files)
    labels = [c.text() for c in panel.strip.shown_chips]
    assert labels == ["PDF Sheet", "PDF Key", "DOCX Sheet", "DOCX Key"]
    assert all(c.isVisibleTo(panel) for c in panel.strip.shown_chips)
    assert panel.strip.folder_chip.text() == "Folder"
    assert panel.strip.folder_chip.toolTip() == str(result.files[0].parent)
    # A chip opens its file in its own app (the library's opener, never parsed);
    # right-click shows it in Finder.
    opened: list[Path] = []
    revealed: list[Path] = []
    monkeypatch.setattr(window.library, "open_externally", opened.append)
    monkeypatch.setattr(window.library, "reveal", revealed.append)
    docx = next(c for c in panel.strip.chips if c.text() == "DOCX Key")
    qtbot.mouseClick(docx, Qt.MouseButton.LeftButton)
    assert opened == [next(f for f in result.files if f.name.endswith("_key.docx"))]
    docx.customContextMenuRequested.emit(QPoint(2, 2))
    assert revealed == opened
    # The summary (every file, the folder) is still in the run log.
    assert result.summary in panel.results.log_view.toPlainText()


def test_failure_shows_the_message_and_no_chips(
    window: MainWindow, qtbot: QtBot, tmp_path: Path
) -> None:
    notes = tmp_path / "notes.txt"
    notes.write_text("Lesson 3: while loops\n")
    panel = open_tool(window, "marks")
    panel.set_input_path("marks", notes)
    run(panel, qtbot, ok=False)
    assert panel.strip.state == "danger"
    assert "notes.txt" in panel.strip.text()
    assert not panel.strip.chips and not panel.strip.folder_chip.isVisibleTo(panel)
    assert panel.strip.text() in panel.results.log_view.toPlainText()


def test_missing_inputs_show_in_the_strip(window: MainWindow) -> None:
    panel = open_tool(window, "classroom")
    panel.start_run()
    assert panel.strip.state == "danger"
    assert panel.strip.text().startswith("Fill in: ")


def test_warnings_are_a_count_that_opens(
    window: MainWindow, qtbot: QtBot, example_marks_messy: Path, example_marks_max: Path
) -> None:
    panel = open_tool(window, "marks")
    panel.set_input_path("marks", example_marks_messy)
    run(panel, qtbot)
    strip = panel.strip
    n = len(strip.warnings)
    assert n >= 2
    assert strip.warning_toggle.isVisibleTo(panel)
    assert strip.warning_toggle.text() == f"{n} warnings ▸"
    assert not strip.warning_list.isVisibleTo(panel)
    strip.warning_toggle.click()
    assert strip.warning_list.isVisibleTo(panel)
    assert strip.warning_toggle.text().endswith("▾")
    for warning in strip.warnings:
        assert warning in strip.warning_list.text()
        assert f"Warning: {warning}" in panel.results.log_view.toPlainText()
    # The next run starts the count again.
    panel.set_input_path("marks", example_marks_max)
    run(panel, qtbot)
    assert not strip.warnings and not strip.warning_toggle.isVisibleTo(panel)
    assert [c.text() for c in strip.shown_chips] == [
        "CSV Distribution",
        "CSV Questions",
        "PNG Chart",
    ]


def test_details_is_remembered_per_tool(window: MainWindow, qtbot: QtBot) -> None:
    worksheet = open_tool(window, "worksheet")
    assert not worksheet.results.details_open
    worksheet.results.details_toggle.click()
    assert worksheet.results.log_view.isVisibleTo(worksheet)
    assert worksheet.results.details_toggle.text() == "Details ▾"
    run(worksheet, qtbot)
    assert worksheet.results.details_open  # a run does not close it
    # Another tool keeps its own setting; a new panel for the same tool
    # (the window rebuilt in the same session) opens as it was left.
    assert not open_tool(window, "parsons").results.details_open
    again = ToolPanel(worksheet.plugin, window.config, resources=window.library)
    qtbot.addWidget(again)
    assert again.results.details_open
    # The one-line footer shows the latest log line while closed.
    worksheet.results.details_toggle.click()
    assert worksheet.results.log_tail.text() == worksheet.last_result.summary  # type: ignore[union-attr]


def test_more_files_than_fit_go_under_more(qtbot: QtBot, tmp_path: Path) -> None:
    strip = ResultStrip()
    qtbot.addWidget(strip)
    files = [tmp_path / f"year9_bug{i}.py" for i in range(1, 7)]
    files += [tmp_path / "year9_bugs.pdf", tmp_path / "year9_bugs_key.pdf"]
    strip.resize(1000, 80)
    strip.show()
    strip.show_result(RunResult(files=files, outcome="6 buggy versions · lines 1, 2"))
    QApplication.processEvents()
    assert len(strip.chips) == len(files) == len(file_chips(files))
    assert len(strip.shown_chips) == MAX_CHIPS
    assert [c.text() for c in strip.shown_chips[:2]] == ["PDF Sheet", "PDF Key"]
    assert strip.more.isVisible() and strip.more.text() == f"+{len(files) - MAX_CHIPS} more"
    # Narrower: fewer chips in the line, never one squeezed; the rest under "more".
    strip.resize(300, 80)
    QApplication.processEvents()
    assert 0 < len(strip.shown_chips) < MAX_CHIPS
    for chip in strip.shown_chips:
        assert chip.width() >= chip.sizeHint().width(), chip.text()
    assert strip.more.text() == f"+{len(files) - len(strip.shown_chips)} more"


def test_a_long_outcome_wraps_and_is_never_cut_mid_word(qtbot: QtBot, tmp_path: Path) -> None:
    strip = ResultStrip()
    qtbot.addWidget(strip)
    long = " ".join(["Wrote binary_medium_s42.pdf to the outputs folder"] * 8)
    strip.show_result(RunResult(summary=long, files=[tmp_path / "a.pdf"]))
    strip.resize(520, 120)
    strip.show()
    QApplication.processEvents()
    assert strip.text() == long  # the whole text is kept (tooltip, tests, the log)
    shown = QLabel.text(strip.message)
    lines = shown.split("\n")
    assert len(lines) == 2 and lines[-1].endswith(" …")
    words = set(long.split())
    assert all(w in words for w in shown.replace("…", "").split())
    assert strip.message.toolTip() == long


def test_elided_label_whole_words(qtbot: QtBot) -> None:
    label = ElidedLabel(max_lines=1, whole_words=True)
    qtbot.addWidget(label)
    label.resize(120, 20)
    label.setText("scripts graded with three warnings in the log")
    shown = QLabel.text(label)
    assert shown.endswith(" …") and shown != label.text()
    assert all(w in label.text().split() for w in shown.removesuffix(" …").split())


# A failure the teacher must read to the end: three sentences, the last one
# saying what to do (#121). Longer than two lines at the minimum window width.
LONG_FAILURE = (
    "Could not read marks_week3.csv: the column q7 has a value that is not a number "
    "on row 12. Check the file in Numbers or Excel, fix that value or leave it blank, "
    "and save it as CSV again. Then choose the file here and press Analyse."
)


def _assert_fits(strip: ResultStrip) -> list[str]:
    """Every line of the message is inside the label, and the label inside
    the strip: no glyph is clipped at either edge. Returns the lines."""
    label = strip.message
    lines = QLabel.text(label).split("\n")
    metrics = label.fontMetrics()
    inside = label.contentsRect()
    assert inside.height() >= len(lines) * metrics.lineSpacing(), (inside, lines)
    assert all(metrics.horizontalAdvance(line) <= inside.width() for line in lines), lines
    box = label.geometry()
    assert box.top() >= 0 and box.bottom() < strip.height(), (box, strip.height())
    return lines


def test_a_long_failure_shows_whole_and_the_strip_grows(
    narrow_window: MainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, example_marks: Path
) -> None:
    panel = open_tool(narrow_window, "marks")
    one_line = panel.strip.height()

    def fail(*_args: object) -> RunResult:
        raise ToolError(LONG_FAILURE)

    monkeypatch.setattr(panel.plugin, "run", fail)
    panel.set_input_path("marks", example_marks)
    run(panel, qtbot, ok=False)
    strip = panel.strip
    assert strip.state == "danger" and strip.text() == LONG_FAILURE
    lines = _assert_fits(strip)
    # Whole: every word, in order, nothing cut; as many lines as it needs.
    assert 2 < len(lines) <= FAILURE_LINES
    assert " ".join(lines) == LONG_FAILURE
    assert strip.message.toolTip() == ""
    assert strip.height() > one_line
    # Wider, then back: it rewraps each time and the strip follows.
    narrow_window.resize(1600, 900)
    QApplication.processEvents()
    assert " ".join(_assert_fits(strip)) == LONG_FAILURE
    narrow_window.resize(narrow_window.minimumSize())
    QApplication.processEvents()
    assert len(_assert_fits(strip)) == len(lines)
    # The next run puts the strip back to one line.
    monkeypatch.undo()
    run(panel, qtbot)
    assert strip.message.max_lines == 2
    assert len(_assert_fits(strip)) == 1


def test_a_failure_past_the_cap_is_cut_between_words_with_a_tooltip(qtbot: QtBot) -> None:
    strip = ResultStrip()
    qtbot.addWidget(strip)
    strip.resize(520, 60)
    strip.show()
    endless = " ".join([LONG_FAILURE] * 6)
    strip.show_failure(endless)
    QApplication.processEvents()
    lines = _assert_fits(strip)
    assert len(lines) == FAILURE_LINES and lines[-1].endswith(" …")
    words = set(endless.split())
    assert all(w in words for w in " ".join(lines).removesuffix(" …").split())
    assert strip.message.toolTip() == endless  # and the whole text is in Details


def test_a_200_character_failure_is_whole_at_the_default_width(
    window: MainWindow, qtbot: QtBot
) -> None:
    panel = open_tool(window, "marks")
    message = (LONG_FAILURE * 2)[:200].rsplit(" ", 1)[0] + "."
    panel.strip.show_failure(message)
    QApplication.processEvents()
    lines = _assert_fits(panel.strip)
    assert " ".join(lines) == message and "…" not in message
