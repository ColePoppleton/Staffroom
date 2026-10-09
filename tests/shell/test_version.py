"""The running version is visible in the window (#69): the sidebar header
under the app name, and Settings > Updates with the commit off a release tag."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from staffroom import __version__
from staffroom.core.config import load_config
from staffroom.core.discovery import visible_plugins
from staffroom.core.update import UpdateStatus
from staffroom.shell.settings_page import SettingsPage
from staffroom.shell.sidebar import Sidebar


def test_sidebar_header_shows_the_version_and_tool_count(qtbot: QtBot) -> None:
    plugins = visible_plugins()
    sidebar = Sidebar(plugins)
    qtbot.addWidget(sidebar)
    text = sidebar.brand_sub.text()
    assert __version__ in text
    assert text == f"v{__version__} · {len(plugins)} tools"


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
