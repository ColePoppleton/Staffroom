"""First run: with no resources folder set, the launcher opens on one card that
asks for it. Choosing a folder saves it, indexes it with progress and lands on
the first workflow tool; "Not now" lands there too and leaves the sidebar hint.
The card never suggests a folder, cloud-synced or otherwise."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom.core import paths
from staffroom.core.config import load_config
from staffroom.core.library.service import LibraryService
from staffroom.shell.app import build_window, parse_args
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel
from staffroom.shell.widgets import FirstRunCard

CLOUD_WORDS = ("onedrive", "icloud", "google drive", "dropbox", "sharepoint")


@pytest.fixture
def fresh_window(qtbot: QtBot, tmp_path: Path) -> MainWindow:
    config = load_config()  # no config file: resources_root is empty
    assert config.general.resources_root == ""
    library = LibraryService(Path(""), tmp_path / "library.db")
    # auto_index=False only skips the start-up update check here: the root is
    # unset, so there is nothing to index until the card's folder is chosen.
    win = MainWindow(config, library=library, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    return win


def _card_text(card: FirstRunCard) -> str:
    return " ".join(label.text() for label in card.labels()).lower()


def test_fresh_install_opens_on_the_first_run_card(fresh_window: MainWindow) -> None:
    win = fresh_window
    assert win.first_run is not None
    assert win.stack.currentWidget() is win.first_run
    assert win.sidebar.list.currentRow() == -1  # no tool chosen yet
    text = _card_text(win.first_run)
    assert "choose your resources folder" in text
    assert "settings" in text
    assert "what the resource library stores" in text
    # The sessions-folder default is shown as text, as written in the config default.
    assert paths.DEFAULT_SESSIONS_ROOT.lower() in text
    assert str(Path.home()) not in text  # never the expanded home path in a screenshot
    assert win.first_run.choose_button.text() == "Choose…"
    assert win.first_run.later_button.text() == "Not now"
    assert win.sidebar.resources.status.text() == "No folder chosen: set it in Settings"


def test_card_suggests_no_folder(fresh_window: MainWindow) -> None:
    card = fresh_window.first_run
    assert card is not None
    assert card.picker.edit.text() == ""
    assert card.picker.edit.placeholderText() == "Choose a folder…"
    text = _card_text(card) + " " + card.picker.edit.placeholderText().lower()
    assert not any(word in text for word in CLOUD_WORDS)
    assert card.picker._last_dir == str(Path.home())  # the dialog starts at home, no hint


def test_not_now_lands_on_the_first_tool_and_keeps_the_hint(fresh_window: MainWindow) -> None:
    win = fresh_window
    assert win.first_run is not None
    win.first_run.later_button.click()
    panel = win.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == "classroom"
    assert win.config.general.resources_root == ""
    assert load_config().general.resources_root == ""
    assert win.sidebar.resources.status.text() == "No folder chosen: set it in Settings"
    # Nothing else was written: the config holds only what the tool switch saved.
    assert load_config().general.last_tool == "classroom"


def test_choosing_a_folder_saves_indexes_and_lands_on_the_first_tool(
    fresh_window: MainWindow, qtbot: QtBot, resources_root: Path
) -> None:
    win = fresh_window
    assert win.first_run is not None
    with qtbot.waitSignal(win.library_page.indexed, timeout=10000):
        win.first_run.picker.set_path(resources_root)
    assert win.config.general.resources_root == str(resources_root)
    assert load_config().general.resources_root == str(resources_root)
    assert win.settings.resources_root.edit.text() == str(resources_root)
    assert win.library.root == resources_root.resolve()
    assert win.library.count() > 0
    panel = win.stack.currentWidget()
    assert isinstance(panel, ToolPanel) and panel.plugin.name == "classroom"
    assert win.sidebar.resources.status.text().endswith("files")
    assert win.first_run.progress.value() == win.first_run.progress.maximum()


def test_card_shows_progress_while_indexing(
    fresh_window: MainWindow, qtbot: QtBot, resources_root: Path
) -> None:
    card = fresh_window.first_run
    assert card is not None
    assert card.progress.isHidden()
    with qtbot.waitSignal(fresh_window.library_page.indexed, timeout=10000):
        card.picker.set_path(resources_root)
        assert not card.progress.isHidden()
        assert card.picker.isEnabled() is False  # the folder is taken; no second pick
        assert card.later_button.text() == "Continue"
        assert "Indexing" in card.status.text()


def test_a_folder_that_does_not_exist_is_refused(fresh_window: MainWindow, tmp_path: Path) -> None:
    card = fresh_window.first_run
    assert card is not None
    card.picker.set_path(tmp_path / "nope")
    assert fresh_window.stack.currentWidget() is card
    assert fresh_window.config.general.resources_root == ""
    assert not card.hint.isHidden()
    assert "does not exist" in card.hint.text()


def test_configured_root_shows_no_card(qtbot: QtBot, tmp_path: Path) -> None:
    config = load_config()
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False)
    qtbot.addWidget(win)
    assert win.first_run is None
    assert isinstance(win.stack.currentWidget(), ToolPanel)
    assert win.sidebar.resources.status.text() == "Folder not found: set it in Settings"


def test_first_run_flag_forces_the_card_for_screenshots(qtbot: QtBot, tmp_path: Path) -> None:
    config = load_config()
    config.general.resources_root = str(tmp_path / "resources")
    config.save()
    args = parse_args(["--first-run", "--screenshot", str(tmp_path / "s.png")])
    win = build_window(args)
    qtbot.addWidget(win)
    assert win.first_run is not None
    assert win.stack.currentWidget() is win.first_run
    assert load_config().general.resources_root == str(tmp_path / "resources")  # untouched
