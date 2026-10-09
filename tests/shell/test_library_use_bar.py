"""The Library hands a file to a tool (#88): the use bar under a file's
title offers Open for class (Classroom's own run, on a copy) and one button
per tool whose main file input takes this kind of file, read from the tools'
own panel specs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core import launch
from staffroom.core.config import load_config
from staffroom.core.discovery import discover_plugins
from staffroom.core.library.service import LibraryService
from staffroom.core.panel import PanelSpec, ResourcePicker
from staffroom.core.plugin import RunContext, RunResult
from staffroom.shell.library.use_bar import LABEL_HINT
from staffroom.shell.main_window import MainWindow
from staffroom.shell.sidebar import LIBRARY
from staffroom.shell.tool_panel import ToolPanel

CODE_TOOLS = ["parsons", "trace", "bugs", "fade", "pseudocode"]
PY = "Python/Python_Course/while_loops.py"


@pytest.fixture
def runs(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """The editor launches Classroom makes, instead of opening Thonny."""
    calls: list[list[str]] = []
    monkeypatch.setattr(launch, "_popen", lambda argv: calls.append(list(argv)))
    return calls


def make_window(
    qtbot: QtBot,
    service: LibraryService,
    resources_root: Path,
    tmp_path: Path,
    plugins: tuple[Any, ...] | None = None,
) -> MainWindow:
    config = load_config()
    config.general.resources_root = str(resources_root)
    config.general.sessions_root = str(tmp_path / "sessions")
    win = MainWindow(config, plugins=plugins, library=service, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    return win


@pytest.fixture
def window(
    qtbot: QtBot, service: LibraryService, resources_root: Path, tmp_path: Path
) -> MainWindow:
    return make_window(qtbot, service, resources_root, tmp_path)


def select(window: MainWindow, rel_path: str) -> None:
    """What the teacher does: click the file in the Library's tree."""
    window.show_library()
    window.resources.select(rel_path)
    assert window.library_page.preview.resource is not None
    assert window.library_page.preview.resource.rel_path == rel_path


# -- which tools ------------------------------------------------------------
def test_a_python_file_offers_the_five_code_tools(window: MainWindow) -> None:
    select(window, PY)
    bar = window.use_bar
    assert bar.visible_tools() == CODE_TOOLS
    assert bar.class_group.isVisibleTo(bar)  # Open for class, with its label field
    assert not bar.open_button.isVisibleTo(bar)
    # Hidden tools never appear, Classroom is Open for class, not a button.
    assert "hello" not in bar.buttons and "classroom" not in bar.buttons
    assert [bar.buttons[n].text() for n in CODE_TOOLS] == [
        "Parsons",
        "Trace",
        "Bugs",
        "Fade",
        "Pseudocode",
    ]


@pytest.mark.parametrize(
    ("rel_path", "tools"),
    [
        ("Python/notes.md", ["quiz"]),
        ("Python/marks.csv", ["marks"]),
        ("Python/readme.txt", ["pseudocode"]),
        ("Scratch/diagram.png", []),
        ("Python/OCR Booklet/booklet.pdf", []),
    ],
)
def test_each_kind_offers_the_tools_that_take_it(
    window: MainWindow, rel_path: str, tools: list[str]
) -> None:
    select(window, rel_path)
    assert window.use_bar.visible_tools() == tools


def test_open_for_class_only_for_files_the_editor_opens(window: MainWindow) -> None:
    """Classroom opens the copy in the teacher's editor: offered for code and
    text, not for a PDF or an image (Open externally is the main action)."""
    bar = window.use_bar
    for rel in (PY, "Python/notes.md", "Python/marks.csv", "Python/readme.txt"):
        select(window, rel)
        assert bar.class_group.isVisibleTo(bar), rel
    for rel in ("Scratch/diagram.png", "Python/OCR Booklet/booklet.pdf"):
        select(window, rel)
        assert not bar.class_group.isVisibleTo(bar), rel
        assert bar.open_button.isVisibleTo(bar), rel


def test_a_new_tool_appears_with_no_library_change(
    qtbot: QtBot, service: LibraryService, resources_root: Path, tmp_path: Path
) -> None:
    """The bar is built from the tools' own input specs: a tool that declares
    ``.sb`` is offered for a Scratch file."""

    class ScratchTool:
        name = "scratchy"
        description = "Does something with a Scratch project."
        version = "0.1.0"
        group, glyph = "From a program", "tool"

        def register_cli(self, app: Any) -> None:
            pass

        def panel_spec(self) -> PanelSpec:
            return PanelSpec(
                title="Scratchy",
                inputs=(ResourcePicker(key="project", label="Project", filter_ext=".sb"),),
            )

        def run(self, inputs: Any, ctx: RunContext) -> RunResult:
            return RunResult(summary="ok")

    plugins = (*discover_plugins(), ScratchTool())
    win = make_window(qtbot, service, resources_root, tmp_path, plugins=plugins)
    select(win, "Scratch/flappy.sb")
    assert win.use_bar.visible_tools() == ["scratchy"]
    win.use_bar.buttons["scratchy"].click()
    panel = win.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == "scratchy"
    assert panel.resource_pickers["project"].value() == resources_root / "Scratch/flappy.sb"


def test_files_with_pupil_details_or_not_on_this_mac_go_nowhere(
    window: MainWindow, qtbot: QtBot, resources_root: Path
) -> None:
    """A file indexed by name only (it looks like it holds pupil details) is
    not copied for class or handed to a tool; nor is a cloud-only one."""
    (resources_root / "Python" / "task_submission.py").write_text(
        "# Candidate number: 4021\n# UPN: A123456789012\nprint(1)\n"
    )
    with qtbot.waitSignal(window.library_page.indexed, timeout=10000):
        window.resources.reindex.click()
    bar = window.use_bar
    for rel in ("Python/task_submission.py", "Python/cloud_file.py"):
        window.library_page.show_resource(rel)
        assert bar.visible_tools() == [], rel
        assert not bar.class_group.isVisibleTo(bar), rel
        assert bar.open_button.isVisibleTo(bar), rel


# -- handing over -------------------------------------------------------------
def test_clicking_trace_lands_on_trace_with_the_file_picked(
    window: MainWindow, resources_root: Path
) -> None:
    select(window, PY)
    window.use_bar.buttons["trace"].click()
    panel = window.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == "trace"
    assert window.sidebar.current() == "trace"
    assert panel.code_sources["source"].value().path == resources_root / PY
    assert "while count < 10" in panel.code_sources["source"].value().text  # shown at once


def test_marks_takes_a_csv_through_its_file_picker(
    window: MainWindow, resources_root: Path
) -> None:
    select(window, "Python/marks.csv")
    window.use_bar.buttons["marks"].click()
    panel = window.panel_for("marks")
    assert window.stack.currentWidget() is panel
    assert panel.pickers["marks"].value() == resources_root / "Python/marks.csv"


# -- open for class -----------------------------------------------------------
def test_open_for_class_is_three_actions_through_classrooms_run(
    window: MainWindow, qtbot: QtBot, resources_root: Path, tmp_path: Path, runs: list[list[str]]
) -> None:
    """Select the file, type the label, press Enter: a copy in today's session
    folder, opened in the editor, made by Classroom's own run. The original
    is untouched and the Library stays in view."""
    original = resources_root / PY
    before = original.read_bytes()
    select(window, PY)  # 1
    bar = window.use_bar
    bar.label.setText("P3 Y9 loops")  # 2
    panel = window.panel_for("classroom")
    with qtbot.waitSignal(panel.run_finished, timeout=10000) as finished:
        bar.label.returnPressed.emit()  # 3: Enter
    assert finished.args == [True]

    copies = list((tmp_path / "sessions").glob("*/P3 Y9 loops/while_loops.py"))
    assert len(copies) == 1
    assert copies[0].read_bytes() == before
    assert original.read_bytes() == before  # never touched
    assert runs and str(copies[0]) in runs[-1]  # the editor opened the copy
    assert panel.last_result is not None and panel.last_result.files == [copies[0]]
    assert window.stack.currentWidget() is window.library_page
    assert window.sidebar.current() == LIBRARY
    assert bar.status_box.isVisibleTo(bar) and "P3 Y9 loops" in bar.status.text()
    assert bar.classroom_link.isVisibleTo(bar)
    bar.classroom_link.click()
    assert window.stack.currentWidget() is panel
    table = panel.results.action_tables["sessions"]
    assert table.model.rowCount() == 1  # today's session, listed in Classroom


def test_open_for_class_asks_for_a_label_first(
    window: MainWindow, runs: list[list[str]], tmp_path: Path
) -> None:
    select(window, PY)
    bar = window.use_bar
    bar.class_button.click()
    assert bar.status.text() == LABEL_HINT
    assert not (tmp_path / "sessions").exists()
    assert runs == []


def test_a_failed_copy_says_why(
    window: MainWindow, qtbot: QtBot, resources_root: Path, runs: list[list[str]]
) -> None:
    """Classroom's own errors come back to the use bar (here the file went
    away after it was indexed)."""
    select(window, "Python/readme.txt")
    (resources_root / "Python" / "readme.txt").unlink()
    bar = window.use_bar
    bar.label.setText("P2 Y7 text")
    with qtbot.waitSignal(window.panel_for("classroom").run_finished, timeout=10000) as done:
        bar.submit()
    assert done.args == [False]
    assert bar.status.property("role") == "danger"
    assert "readme.txt" in bar.status.text()
    assert not bar.classroom_link.isVisibleTo(bar)
    assert runs == []


def test_cmd_o_on_the_library_opens_the_shown_file_for_class(
    window: MainWindow, qtbot: QtBot, tmp_path: Path, runs: list[list[str]]
) -> None:
    select(window, PY)
    bar = window.use_bar
    window.open_for_class()  # ⌘O with no label yet: the cursor goes to the label
    assert bar.label.hasFocus() or window.focusWidget() is bar.label
    assert window.stack.currentWidget() is window.library_page
    bar.label.setText("P4 Y8 while")
    with qtbot.waitSignal(window.panel_for("classroom").run_finished, timeout=10000):
        window.open_for_class()  # ⌘O again: opens it
    assert list((tmp_path / "sessions").glob("*/P4 Y8 while/while_loops.py"))


def test_cmd_o_elsewhere_still_opens_classroom(window: MainWindow, monkeypatch: Any) -> None:
    picked: list[bool] = []
    window.sidebar.select("marks")
    panel = window.panel_for("classroom")
    monkeypatch.setattr(
        panel.resource_pickers["resource"], "pick_from_library", lambda: picked.append(True)
    )
    window.open_for_class()
    assert window.stack.currentWidget() is panel and picked == [True]


# -- the window's width (#103) -------------------------------------------------
def test_a_long_resources_path_does_not_widen_the_window(
    qtbot: QtBot, resources_root: Path, tmp_path: Path, opened: list[list[str]]
) -> None:
    deep = tmp_path
    while len(str(deep)) < 200:
        deep = deep / "A department shared drive folder"
    deep.mkdir(parents=True)
    service = LibraryService(deep, tmp_path / "deep.db", opener=lambda a: opened.append(list(a)))
    win = make_window(qtbot, service, deep, tmp_path)
    win.show_library()
    assert len(str(deep)) >= 200
    assert win.library_page.subtitle.toolTip() == str(deep)
    assert win.minimumSizeHint().width() <= 1040
    service.set_root(tmp_path / "gone" / deep.relative_to(tmp_path))  # folder not found
    win.refresh_resources()
    win.library_page.reindex()
    assert win.minimumSizeHint().width() <= 1040
