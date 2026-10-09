"""The running version is visible in the window (#69): the sidebar footer
(since #89), and Settings > Updates with the commit off a release tag."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from staffroom import __version__
from staffroom.core.config import load_config
from staffroom.core.discovery import visible_plugins
from staffroom.core.update import UpdateStatus
from staffroom.shell.settings_page import SettingsPage
from staffroom.shell.sidebar import Sidebar


def test_sidebar_footer_shows_the_version_and_update_state(qtbot: QtBot) -> None:
    """The version moved from under the brand to the footer (#89) and says
    whether a release is waiting once Settings has checked."""
    sidebar = Sidebar(visible_plugins())
    qtbot.addWidget(sidebar)
    assert sidebar.version_label.text() == f"v{__version__}"  # not checked yet
    sidebar.set_update_available(False)
    assert sidebar.version_label.text() == f"v{__version__} · up to date"
    assert sidebar.update_button.isHidden()
    sidebar.set_update_available(True)
    assert sidebar.version_label.text().startswith(f"v{__version__}")
    assert not sidebar.update_button.isHidden()
    with qtbot.waitSignal(sidebar.settings_requested):
        sidebar.update_button.click()


def test_settings_updates_card_states_the_running_version(qtbot: QtBot) -> None:
    page = SettingsPage(load_config())
    qtbot.addWidget(page)
    assert page.version_label.text() == f"Running Staffroom {__version__}"

    def status(**kw: object) -> UpdateStatus:
        base: dict[str, object] = {
            "repo": Path("/repo"),
            "commit": "a1b2c3d",
            "branch": "dev",
            "remote": "origin/main",
            "behind": 0,
            "ahead": 3,
            "dirty": False,
        }
        return UpdateStatus(**{**base, **kw})  # type: ignore[arg-type]

    page._on_update_status(status())
    assert page.version_label.text() == f"Running Staffroom {__version__} (dev, a1b2c3d)"
    page._on_update_status(status(branch="main", ahead=0, head_tag=f"v{__version__}"))
    assert page.version_label.text() == f"Running Staffroom {__version__}"
