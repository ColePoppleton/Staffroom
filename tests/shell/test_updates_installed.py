"""Settings > Updates and the sidebar footer for an installed copy (#9):
no check, no git, the one line on how to update, and a footer that never
says "up to date" without having checked."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from staffroom import __version__
from staffroom.core import install, update
from staffroom.core.config import load_config
from staffroom.core.install import Installation, InstallKind
from staffroom.core.update import UpdateStatus
from staffroom.shell import update_worker
from staffroom.shell.main_window import MainWindow
from staffroom.shell.settings_page import SettingsPage

COMMAND = "uv tool upgrade staffroom"


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "tools" / "staffroom" / "lib" / "python3.12" / "site-packages"
    monkeypatch.setattr(
        install,
        "detect",
        lambda package_dir=None: Installation(InstallKind.UV_TOOL, package / "staffroom"),
    )

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"an installed copy started {args}")

    monkeypatch.setattr(update.subprocess, "run", refuse)
    monkeypatch.setattr(update_worker.UpdateWorker, "start", refuse)
    monkeypatch.setattr(update_worker.ApplyWorker, "start", refuse)


@pytest.mark.usefixtures("installed")
def test_settings_card_on_an_installed_copy_shows_the_command_and_no_buttons(
    qtbot: QtBot,
) -> None:
    page = SettingsPage(load_config())
    qtbot.addWidget(page)
    assert COMMAND in page.update_status.text()
    assert "Could not check" not in page.update_status.text()
    assert page.check_button.isHidden() and page.update_button.isHidden()
    with qtbot.waitSignal(page.update_available) as signal:
        page.check_updates(fetch=True)  # what the window does at start
    assert signal.args == [None]
    assert page.version_label.text() == f"Running Staffroom {__version__}"


@pytest.mark.usefixtures("installed")
def test_installed_copy_starts_without_a_check_and_footer_shows_only_the_version(
    qtbot: QtBot,
) -> None:
    win = MainWindow(load_config(), auto_index=True)  # the real start path
    qtbot.addWidget(win)
    assert win.sidebar.version_label.text() == f"v{__version__}"
    assert win.sidebar.update_button.isHidden()
    assert COMMAND in win.settings.update_status.text()


def test_a_failed_check_never_reads_up_to_date(qtbot: QtBot) -> None:
    page = SettingsPage(load_config())
    qtbot.addWidget(page)
    failed = UpdateStatus(Path("/r"), "?", "?", "", 0, 0, False, error="no network")
    with qtbot.waitSignal(page.update_available) as signal:
        page._on_update_status(failed)
    assert signal.args == [None]
    assert page.update_status.text() == "Could not check: no network"
