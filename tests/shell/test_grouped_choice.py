"""The lesson list (#75): a GroupedChoice of units and lessons, greyed by board."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.core.panel import GroupedChoice, GroupedItem, ItemGroup, PanelSpec, shown_when
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets.grouped_choice import GroupedChoiceWidget, ListRow

SPEC = GroupedChoice(
    key="pick",
    label="Unit",
    items_label="Lesson",
    groups=(
        ItemGroup("a", "A", (GroupedItem("a/1", "One", tag="1.1"), GroupedItem("a/2", "Two"))),
        ItemGroup(
            "b",
            "B",
            (
                GroupedItem("b/1", "Faint", dim=True, note="Elsewhere only"),
                GroupedItem("b/2", "Plain"),
                GroupedItem("b/r", "Review", divided=True),
            ),
        ),
    ),
)


def test_spec_refuses_repeats_and_unknown_defaults() -> None:
    item = GroupedItem("x", "X")
    with pytest.raises(ValueError, match="each value once"):
        GroupedChoice("k", "L", "I", (ItemGroup("g", "G", (item, item)),))
    with pytest.raises(ValueError, match="not an item"):
        GroupedChoice("k", "L", "I", (ItemGroup("g", "G", (item,)),), default="y")
    assert SPEC.initial == "a/1" and SPEC.group_of("b/2").value == "b"  # type: ignore[union-attr]


def test_a_condition_can_read_a_grouped_choice() -> None:
    spec = PanelSpec(title="T", inputs=(SPEC,), shown_when={})
    assert spec._condition_source("pick") is not None
    with pytest.raises(ValueError, match="can never be"):
        PanelSpec(
            title="T",
            inputs=(
                SPEC,
                GroupedChoice(
                    "other",
                    "O",
                    "I",
                    SPEC.groups[:1] and (ItemGroup("z", "Z", (GroupedItem("z/1", "Z"),)),),
                ),
            ),
            shown_when={"other": shown_when("pick", "nope")},
        )


def test_chip_shows_the_groups_rows_and_skips_a_dim_first_row(qtbot: QtBot) -> None:
    widget = GroupedChoiceWidget(SPEC)
    qtbot.addWidget(widget)
    assert widget.value() == "a/1" and list(widget.rows) == ["a/1", "a/2"]
    with qtbot.waitSignal(widget.changed) as blocker:
        widget.chips["b"].click()
    assert blocker.args == ["b/2"]  # the first row that is not faint
    assert list(widget.rows) == ["b/1", "b/2", "b/r"]
    faint = widget.rows["b/1"]
    assert faint.property("dim") == "true" and faint.tag.text() == "Elsewhere only"
    faint.click()
    assert widget.value() == "b/1"  # faint, but still choosable
    widget.chips["a"].click()
    widget.rows["a/2"].click()
    widget.chips["b"].click()
    assert widget.value() == "b/1"  # each unit remembers its lesson
    widget.chips["a"].click()
    assert widget.value() == "a/2"


def test_rows_say_what_they_are_to_a_screen_reader(qtbot: QtBot) -> None:
    row = ListRow(GroupedItem("v", "Denary to binary", tag="OCR 1.2.4", detail="8 bits"))
    qtbot.addWidget(row)
    assert row.accessibleName() == "Denary to binary, OCR 1.2.4"
    assert row.detail.text() == "8 bits"


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    return win


def test_the_lesson_list_follows_the_board_in_settings(window: MainWindow) -> None:
    window.go_to_tool("worksheet")
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel)
    lesson = panel.grouped["lesson"]
    lesson.chips["twos-complement"].click()  # none on OCR: the first lesson, greyed
    assert lesson.value() == "twos-complement/to-twos-complement"
    assert lesson.rows["twos-complement/review"].property("dim") == "true"
    row = lesson.rows["twos-complement/to-twos-complement"]
    assert row.property("dim") == "true" and row.tag.text() == "On Edexcel only"
    window.config.general.board = "edexcel"  # what Settings does
    window.show_settings()
    window.go_to_tool("worksheet")
    assert lesson.value() == "twos-complement/to-twos-complement"  # kept
    row = lesson.rows["twos-complement/to-twos-complement"]
    assert row.property("dim") == "false" and row.tag.text() == "Edexcel 2.1.3"
    assert "Pearson Edexcel 1CP2" in lesson.note.text()
