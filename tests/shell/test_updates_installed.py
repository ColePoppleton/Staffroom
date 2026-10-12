"""Settings > Updates and the sidebar footer for an installed copy (#9, #11).

An installed copy never runs git. It shows the version running, the newest
release from GitHub's Releases API (a fake here: no test reaches the
network), its notes, and the one command to paste; the footer reads
``v0.8.1 · 0.9.0 out`` only when that is true and never says "up to date"
without a successful check. A checkout keeps its own card.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from staffroom import __version__
from staffroom.core import install, update
from staffroom.core.config import load_config
from staffroom.core.install import Installation, InstallKind
from staffroom.core.update import Release, ReleaseCheck, UpdateStatus
from staffroom.shell import update_worker
from staffroom.shell.main_window import MainWindow
from staffroom.shell.settings_page import SettingsPage

COMMAND = "uv tool upgrade staffroom"
NEWER = "99.0.0"  # always ahead of the running version
PACKAGE = Path("/u/.local/share/uv/tools/staffroom/lib/python3.12/site-packages/staffroom")


def answer(tag: str) -> bytes:
    return json.dumps(
        {
            "tag_name": tag,
            "html_url": f"https://github.com/ColePoppleton/Staffroom/releases/tag/{tag}",
            "published_at": "2026-10-14T10:00:00Z",
            "body": "### Changed\n- **Updates.** Says when a release is out.\n"
            "![a picture](https://example.invalid/x.png)\n",
        }
    ).encode()


class FakeGitHub:
    def __init__(self, body: bytes | None) -> None:
        self.body = body  # None: unreachable
        self.asked = 0

    def __call__(self, url: str, timeout: float) -> bytes:
        assert url == update.RELEASES_API
        self.asked += 1
        if self.body is None:
            raise OSError("no network")
        return self.body


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> None:
    here = Installation(InstallKind.UV_TOOL, PACKAGE)
    monkeypatch.setattr(install, "detect", lambda package_dir=None: here)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"an installed copy started {args}")

    monkeypatch.setattr(update.subprocess, "run", refuse)  # no git, ever
    monkeypatch.setattr(update_worker.UpdateWorker, "start", refuse)
    monkeypatch.setattr(update_worker.ApplyWorker, "start", refuse)


def github(monkeypatch: pytest.MonkeyPatch, body: bytes | None) -> FakeGitHub:
    fake = FakeGitHub(body)
    monkeypatch.setattr(update, "https_get", fake)
    return fake


def checked(page: SettingsPage, qtbot: QtBot) -> None:
    """Press *Check again* and wait for the answer."""
    card = page.installed_updates
    assert card is not None
    with qtbot.waitSignal(card.state_changed, timeout=5000):
        card.check_button.click()
    qtbot.waitUntil(lambda: card._worker is None)


def settings(qtbot: QtBot) -> SettingsPage:
    page = SettingsPage(load_config())
    qtbot.addWidget(page)
    return page


# -- the three states -----------------------------------------------------------


@pytest.mark.usefixtures("installed")
def test_a_newer_release_shows_the_version_notes_and_command(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = github(monkeypatch, answer(f"v{NEWER}"))
    page = settings(qtbot)
    card = page.installed_updates
    assert card is not None
    assert not hasattr(page, "update_button")  # no in-app update for an installed copy
    with qtbot.waitSignal(page.update_available) as footer:
        checked(page, qtbot)
    assert fake.asked == 1
    assert footer.args == [True, f"{NEWER} out"]
    assert card.this_copy.text() == __version__
    assert card.newest.text() == f"{NEWER} · 14 Oct 2026"
    assert card.new_chip.isVisibleTo(card) and card.whats_changed.isVisibleTo(card)
    assert card.steps.text().startswith("To update: quit Staffroom")
    assert card.command_box.command() == COMMAND
    assert card.asked.text().startswith("Checked just now by asking github.com/")
    assert "Nothing about you or your files is sent." in card.asked.text()
    # What changed: the notes, without the picture; the page opens in the browser.
    assert not card.notes_panel.isVisibleTo(card)
    card.whats_changed.click()
    assert card.notes_panel.isVisibleTo(card)
    assert "Says when a release is out." in card.notes.toPlainText()
    assert "picture" not in card.notes.toPlainText()
    opened: list[str] = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    card.open_release.click()
    assert opened == [f"https://github.com/ColePoppleton/Staffroom/releases/tag/v{NEWER}"]


@pytest.mark.usefixtures("installed")
def test_the_newest_release_already_installed_reads_up_to_date(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    github(monkeypatch, answer(f"v{__version__}"))
    page = settings(qtbot)
    card = page.installed_updates
    assert card is not None
    with qtbot.waitSignal(page.update_available) as footer:
        checked(page, qtbot)
    assert footer.args == [False, ""]
    assert card.newest.text().startswith(__version__)
    assert not card.new_chip.isVisibleTo(card)
    assert card.steps.text().startswith("You have the newest release.")
    assert card.command_box.command() == COMMAND


@pytest.mark.usefixtures("installed")
def test_a_failed_check_is_one_muted_sentence_and_never_up_to_date(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    github(monkeypatch, None)
    page = settings(qtbot)
    card = page.installed_updates
    assert card is not None
    with qtbot.waitSignal(page.update_available) as footer:
        checked(page, qtbot)
    assert footer.args == [None, ""]
    assert card.newest.text() == update.UNREACHABLE
    assert card.newest.property("role") == "muted"
    assert "fatal" not in card.newest.text() and "git repository" not in card.newest.text()
    assert "up to date" not in card.newest.text().lower()
    assert not card.new_chip.isVisibleTo(card) and not card.whats_changed.isVisibleTo(card)
    assert card.steps.text().startswith("To update:")
    assert card.asked.text().startswith("Tried just now")
    assert card.check_button.isEnabled() and card.check_button.text() == "Check again"


@pytest.mark.usefixtures("installed")
def test_copy_puts_the_command_on_the_clipboard(qtbot: QtBot) -> None:
    card = settings(qtbot).installed_updates
    assert card is not None
    card.command_box.copy_button.click()
    assert QApplication.clipboard().text() == COMMAND
    assert card.command_box.copy_button.text() == "Copied"


def test_a_copy_pinned_to_a_release_shows_the_install_line(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    pinned = Installation(InstallKind.UV_TOOL, PACKAGE, tracks_main=False)
    monkeypatch.setattr(install, "detect", lambda package_dir=None: pinned)
    card = settings(qtbot).installed_updates
    assert card is not None
    assert card.command_box.command() == install.INSTALL_LINE
    assert card.pinned_note.isVisibleTo(card)


def test_a_pip_copy_has_no_command_but_still_learns_of_releases(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    other = Installation(InstallKind.OTHER, PACKAGE)
    monkeypatch.setattr(install, "detect", lambda package_dir=None: other)
    card = settings(qtbot).installed_updates
    assert card is not None
    assert not card.command_box.isVisibleTo(card)
    assert card.steps.text() == other.update_hint()


# -- when it asks ---------------------------------------------------------------


@pytest.mark.usefixtures("installed")
def test_the_start_check_asks_once_a_day_and_the_footer_shows_the_last_answer(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = github(monkeypatch, answer(f"v{NEWER}"))
    update.save_release_check(
        ReleaseCheck(
            datetime.now(UTC) - timedelta(hours=2),
            Release(NEWER, f"{update.RELEASES_PAGE}/tag/v{NEWER}", "2026-10-14", "notes"),
        )
    )
    win = MainWindow(load_config(), auto_index=True)  # the real start path
    qtbot.addWidget(win)
    assert fake.asked == 0  # asked two hours ago: not again today
    assert win.sidebar.version_label.text() == f"v{__version__} ·"
    assert win.sidebar.update_button.text() == f"{NEWER} out"
    assert not win.sidebar.update_button.isHidden()
    with qtbot.waitSignal(win.sidebar.updates_requested):
        win.sidebar.update_button.click()
    assert win.stack.currentWidget() is win.settings
    win.wait_for_workers()


@pytest.mark.usefixtures("installed")
def test_a_day_old_answer_is_asked_again_at_start(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = github(monkeypatch, answer(f"v{__version__}"))
    update.save_release_check(
        ReleaseCheck(datetime.now(UTC) - timedelta(days=2), error=update.UNREACHABLE)
    )
    win = MainWindow(load_config(), auto_index=True)
    qtbot.addWidget(win)
    card = win.settings.installed_updates
    assert card is not None
    qtbot.waitUntil(lambda: fake.asked == 1 and card._worker is None, timeout=5000)
    assert win.sidebar.version_label.text() == f"v{__version__} · up to date"
    saved = update.load_release_check()
    assert saved is not None and saved.ok  # kept for the next start


@pytest.mark.usefixtures("installed")
def test_untick_and_the_start_check_never_asks(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = github(monkeypatch, answer(f"v{NEWER}"))
    card = settings(qtbot).installed_updates
    assert card is not None
    assert card.on_start.isChecked()  # on by default
    card.on_start.setChecked(False)
    assert load_config().general.check_for_releases is False  # saved
    win = MainWindow(load_config(), auto_index=True)
    qtbot.addWidget(win)
    assert fake.asked == 0
    assert win.sidebar.version_label.text() == f"v{__version__}"
    checked(win.settings, qtbot)  # Check again still asks
    assert fake.asked == 1


@pytest.mark.usefixtures("installed")
def test_screenshot_mode_never_asks(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = github(monkeypatch, answer(f"v{NEWER}"))
    config = load_config()
    config.read_only = True  # what ``staffroom --screenshot`` sets
    win = MainWindow(config, auto_index=True)
    qtbot.addWidget(win)
    assert fake.asked == 0
    card = win.settings.installed_updates
    assert card is not None and card.newest.text() == "Not checked yet"
    assert card.check_button.text() == "Check now"


# -- a checkout keeps its card -----------------------------------------------------


def test_a_checkout_keeps_its_git_card_and_never_asks_github(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = github(monkeypatch, answer(f"v{NEWER}"))
    page = settings(qtbot)
    assert page.installation.is_checkout  # the test run is this checkout
    assert page.installed_updates is None
    assert page.check_button.text() == "Check for updates"
    assert page.update_button.text() == "Update now"
    failed = UpdateStatus(Path("/r"), "?", "?", "", 0, 0, False, error="no network")
    with qtbot.waitSignal(page.update_available) as signal:
        page._on_update_status(failed)
    assert signal.args == [None, "update"]
    assert page.update_status.text() == "Could not check: no network"
    assert fake.asked == 0


def test_show_updates_scrolls_to_the_card(qtbot: QtBot) -> None:
    page = settings(qtbot)
    page.resize(900, 400)
    page.show()
    qtbot.waitExposed(page)
    page.show_updates()
    bar = page.scroll_area.verticalScrollBar()
    assert bar.value() > 0
    assert bar.value() == min(bar.maximum(), max(0, page.updates_card.y() - 16))
