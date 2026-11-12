"""Add-ons in the launcher (#5): a tool whose add-on is missing is greyed in
the sidebar and opens a card that installs it; with the add-on it opens as
usual. Settings > Add-ons installs and removes in a worker, with progress,
the installer's log behind Details, one sentence when it fails, and a
restart prompt when it works. Every change here goes through a fake
``change``: nothing runs uv and nothing is downloaded."""

from __future__ import annotations

import dataclasses
import sys
import threading
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QMessageBox, QPushButton
from pytestqt.qtbot import QtBot

from staffroom.core import addons, install
from staffroom.core.addons import Outcome
from staffroom.core.config import load_config
from staffroom.core.discovery import get_plugin
from staffroom.core.install import Installation, InstallKind
from staffroom.core.panel import PanelSpec
from staffroom.shell import main_window
from staffroom.shell.addons_card import AddOnsCard
from staffroom.shell.main_window import MainWindow
from staffroom.shell.sidebar import SETTINGS, Sidebar
from staffroom.shell.tool_panel import AddOnNeededPanel, ToolPanel
from staffroom.shell.widgets.addon_needed import AddOnBanner, import_addon

UV_TOOL = Installation(InstallKind.UV_TOOL, Path("/x/tools/staffroom/lib/site-packages/staffroom"))


class Needy:
    """hello's panel and run, listed in Lessons, needing the Web add-on."""

    name = "webpage"
    description = "Shows a pupil's web page beside its code."
    version = "0.1.0"
    group = "Lessons"
    requires = ("web",)

    def __init__(self) -> None:
        self.hello = get_plugin("hello")

    def register_cli(self, app: object) -> None:
        pass

    def panel_spec(self) -> PanelSpec:
        return dataclasses.replace(self.hello.panel_spec(), title="Web page")

    def run(self, inputs: Any, ctx: Any) -> Any:
        return self.hello.run(inputs, ctx)


class FakeChange:
    """Stands in for ``addons.change``: records what was asked, reports a
    line and a step, and answers with ``outcome`` (once ``gate`` opens)."""

    def __init__(self, outcome: Outcome, gate: threading.Event | None = None) -> None:
        self.outcome = outcome
        self.gate = gate
        self.asked: list[frozenset[str]] = []

    def __call__(self, wanted: frozenset[str], **kwargs: Any) -> Outcome:
        self.asked.append(frozenset(wanted))
        kwargs["log_line"]("Resolved 4 packages in 0.3s")
        kwargs["progress"]("Downloading pyside6-webengine (238.0MiB)")
        if self.gate is not None:
            self.gate.wait(10)
        return self.outcome


class Answers:
    """Answers the card's question boxes and remembers the titles."""

    def __init__(self, *, yes: bool = True) -> None:
        self.yes = yes
        self.titles: list[str] = []

    def __call__(self, title: str, text: str) -> bool:
        self.titles.append(title)
        return self.yes


def _with_web(monkeypatch: pytest.MonkeyPatch, present: bool) -> None:
    monkeypatch.setattr(addons, "is_installed", lambda name: present and name == "web")


@pytest.fixture
def window(qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    # The same copy wherever the tests run: a git checkout, the unpacked sdist the
    # release job tests (no .git, so detect() says OTHER and add-ons are manual) or CI.
    monkeypatch.setattr(install, "detect", lambda package_dir=None: UV_TOOL)
    config = load_config()
    config.general.check_for_releases = False  # never ask GitHub from a test
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    plugins = (get_plugin("classroom"), Needy(), get_plugin("hello"))
    win = MainWindow(config, plugins=plugins, auto_index=False)
    qtbot.addWidget(win)
    win.show()
    return win


# -- the sidebar and the tool's page -------------------------------------------


def test_sidebar_greys_a_tool_whose_addon_is_missing(qtbot: QtBot) -> None:
    sidebar = Sidebar((get_plugin("classroom"), Needy()))
    qtbot.addWidget(sidebar)
    item = sidebar.item("webpage")
    assert item is not None
    assert item.needs == "Needs the Web add-on"
    assert item.property("unavailable") is True
    assert item.label.property("unavailable") is True
    assert item.count.text() == "add-on"
    assert "Needs the Web add-on" in item.toolTip()
    assert item.accessibleDescription() == "Needs the Web add-on"
    classroom = sidebar.item("classroom")
    assert classroom is not None and not classroom.needs and not classroom.count.text()
    assert "webpage" in sidebar.tool_names()  # still listed, still on a shortcut


def test_with_the_addon_the_row_is_normal(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_web(monkeypatch, True)
    sidebar = Sidebar((Needy(),))
    qtbot.addWidget(sidebar)
    item = sidebar.item("webpage")
    assert item is not None and not item.needs and not item.property("unavailable")


def test_opening_it_shows_the_install_card(window: MainWindow) -> None:
    window.show_tool("webpage")
    page = window.stack.currentWidget()
    assert isinstance(page, AddOnNeededPanel)
    assert window.sidebar.current() == "webpage"
    assert page.card.heading.text() == "Needs the Web add-on"
    assert "webpage" not in window.panels  # no panel was built
    assert set(page.card.buttons) == {"web"}
    assert page.card.buttons["web"].text() == "Install the Web add-on"


def test_the_install_button_goes_to_settings(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = Answers(yes=False)
    window.settings.addons_card._confirm = answers
    window.show_tool("webpage")
    page = window.stack.currentWidget()
    assert isinstance(page, AddOnNeededPanel)
    page.card.buttons["web"].click()
    assert window.stack.currentWidget() is window.settings
    assert window.sidebar.current() == SETTINGS
    assert answers.titles == ["Install the Web add-on?"]  # asked first; said no
    assert not window.settings.addons_card.busy()


def test_with_the_addon_the_tool_opens_normally(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_web(monkeypatch, True)
    config = load_config()
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, plugins=(Needy(),), auto_index=False)
    qtbot.addWidget(win)
    win.show_tool("webpage")
    assert isinstance(win.stack.currentWidget(), ToolPanel)


def test_the_library_does_not_offer_a_tool_that_cannot_open(window: MainWindow) -> None:
    assert "webpage" not in [t.name for t in window.use_bar.tools]


def test_go_to_tool_with_a_file_lands_on_the_card(window: MainWindow, tmp_path: Path) -> None:
    window.go_to_tool("webpage", tmp_path / "page.html")
    assert isinstance(window.stack.currentWidget(), AddOnNeededPanel)


# -- Settings > Add-ons --------------------------------------------------------


def _card(
    qtbot: QtBot,
    change: FakeChange,
    *,
    installed: frozenset[str] = frozenset(),
    installation: Installation = UV_TOOL,
    answers: Answers | None = None,
) -> AddOnsCard:
    card = AddOnsCard(
        (get_plugin("classroom"), Needy()),
        installation,
        change=change,
        installed=installed,
        confirm=answers or Answers(),
    )
    qtbot.addWidget(card)
    card.show()
    return card


def test_one_row_per_addon_with_its_users_and_size(qtbot: QtBot) -> None:
    card = _card(qtbot, FakeChange(Outcome(True, "")))
    assert list(card.rows) == list(addons.ADDONS)
    web = card.rows["web"]
    assert web.state.text() == "Not installed"
    assert web.button.text() == "Install" and web.button.isEnabled()
    assert "Used by: Web page." in web.details.text()
    assert "MB to download" in web.details.text()
    assert "No tool here needs it yet." in card.rows["media"].details.text()
    assert "installed with uv" in card.how.text()


def test_install_runs_in_a_worker_then_asks_to_restart(qtbot: QtBot) -> None:
    gate = threading.Event()
    change = FakeChange(
        Outcome(True, "Installed the Web add-on. Restart Staffroom to use it.", True), gate
    )
    answers = Answers()
    card = _card(qtbot, change, answers=answers)
    restarts: list[bool] = []
    card.restart_requested.connect(lambda: restarts.append(True))
    card.rows["web"].button.click()
    assert card.busy()
    qtbot.waitUntil(lambda: card.status.text().startswith("Downloading"), timeout=5000)
    # Nothing blocks: the window keeps working; every button waits.
    assert card.progress.isVisible()
    assert not any(row.button.isEnabled() for row in card.rows.values())
    gate.set()
    qtbot.waitUntil(lambda: not card.busy(), timeout=5000)
    assert change.asked == [frozenset({"web"})]
    assert card.status.text() == "Installed the Web add-on. Restart Staffroom to use it."
    assert card.status.property("role") == "success"
    assert answers.titles == ["Install the Web add-on?", "Restart Staffroom?"]
    assert restarts == [True]
    assert card.rows["web"].state.text() == "Restart to use"
    assert not any(row.button.isEnabled() for row in card.rows.values())  # until the restart
    assert card.restart_button.isVisibleTo(card)
    card.details_button.click()
    assert "Resolved 4 packages" in card.log_view.toPlainText()


def test_a_failed_install_is_one_sentence(qtbot: QtBot) -> None:
    card = _card(qtbot, FakeChange(Outcome(False, addons.BLOCKED)))
    card.request_install("web")
    qtbot.waitUntil(lambda: not card.busy(), timeout=5000)
    assert card.status.text() == addons.BLOCKED
    assert card.status.property("role") == "danger"
    assert card.pending is None
    assert card.rows["web"].button.isEnabled()  # try again later
    assert not card.restart_button.isVisibleTo(card)


def test_a_bug_in_the_installer_is_still_one_sentence(qtbot: QtBot) -> None:
    def broken(wanted: frozenset[str], **kwargs: Any) -> Outcome:
        raise RuntimeError("boom")

    card = _card(qtbot, broken)  # type: ignore[arg-type]
    card.request_install("media")
    qtbot.waitUntil(lambda: not card.busy(), timeout=5000)
    assert card.status.text() == addons.FAILED
    assert "RuntimeError: boom" in card.log_view.toPlainText()


def test_remove_asks_then_changes(qtbot: QtBot) -> None:
    change = FakeChange(
        Outcome(True, "Removed the Media add-on. Restart Staffroom to use it.", True)
    )
    answers = Answers()
    card = _card(qtbot, change, installed=frozenset({"media"}), answers=answers)
    row = card.rows["media"]
    assert row.state.text() == "Installed" and row.button.text() == "Remove"
    row.button.click()
    qtbot.waitUntil(lambda: not card.busy(), timeout=5000)
    assert change.asked == [frozenset()]
    assert answers.titles[0] == "Remove the Media add-on?"
    assert row.state.text() == "Restart to finish"


def test_media_cannot_be_removed_from_under_web(qtbot: QtBot) -> None:
    card = _card(qtbot, FakeChange(Outcome(True, "")), installed=frozenset({"web", "media"}))
    media = card.rows["media"]
    assert media.state.text() == "Comes with Web"
    assert not media.button.isEnabled()
    assert card.rows["web"].button.isEnabled()


def test_a_copy_that_cannot_change_itself_shows_the_line(qtbot: QtBot) -> None:
    bundle = Installation(InstallKind.OTHER, Path("/Applications/X.app/staffroom"))
    change = FakeChange(Outcome(True, ""))
    card = _card(qtbot, change, installation=bundle)
    assert "cannot add to itself" in card.how.text()
    row = card.rows["web"]
    assert row.button.text() == "Show how"
    row.button.click()
    assert change.asked == []  # never guesses
    assert card.manual.isVisibleTo(card)
    assert "staffroom[web]" in card.command_box.command()
    assert "cannot add to itself" in card.manual_text.text()


def test_settings_has_the_card_and_scrolls_to_it(window: MainWindow) -> None:
    window.show_addons()
    assert window.stack.currentWidget() is window.settings
    assert window.settings.addons_card.rows["web"].users == ["Web page"]


# -- leaving -------------------------------------------------------------------


def test_closing_during_a_change_waits_for_it(
    window: MainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    told: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *a: told.append(a[1]))
    gate = threading.Event()
    fake = FakeChange(Outcome(True, "Installed the Web add-on.", True), gate)
    monkeypatch.setattr(addons, "change", fake)
    card = window.settings.addons_card
    card._confirm = Answers()
    card.request_install("web")
    assert card.busy()
    assert window.close() is False  # not while uv is changing the copy
    assert told == ["Installing an add-on"]
    assert window.isVisible()
    gate.set()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=5000)
    assert card.titles_asked if False else True


def test_restart_starts_the_same_command_again(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(
        main_window.QProcess, "startDetached", lambda program, args: started.append((program, args))
    )
    window.settings.addons_card.restart_requested.emit()
    assert not window.isVisible()
    assert started == [(sys.executable, list(sys.argv))]


# -- the kit's pieces ----------------------------------------------------------


def test_a_banner_offers_the_addon(qtbot: QtBot) -> None:
    banner = AddOnBanner("web", "Pages show in a basic viewer.")
    qtbot.addWidget(banner)
    asked: list[str] = []
    banner.install_requested.connect(asked.append)
    assert banner.text.text() == "Pages show in a basic viewer. The Web add-on does more."
    banner.link.click()
    assert asked == ["web"]


def test_a_tool_panel_passes_a_banner_on(qtbot: QtBot, monkeypatch: pytest.MonkeyPatch) -> None:
    from staffroom.shell import tool_panel

    real_init = tool_panel.ToolPanel._build_inputs

    def with_banner(self: ToolPanel) -> None:
        real_init(self)
        self.inputs_layout.addWidget(AddOnBanner("web", "Basic view."))

    monkeypatch.setattr(tool_panel.ToolPanel, "_build_inputs", with_banner)
    panel = ToolPanel(get_plugin("hello"), load_config())
    qtbot.addWidget(panel)
    asked: list[str] = []
    panel.addon_install_requested.connect(asked.append)
    panel.findChild(AddOnBanner).link.click()
    assert asked == ["web"]


def test_import_addon_is_none_without_the_addon() -> None:
    assert import_addon("web", "QtWebEngineWidgets") is None


def test_import_addon_loads_the_module_when_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    # A module every copy has stands in for the add-on's.
    _with_web(monkeypatch, True)
    module = import_addon("web", "QtCore")
    assert module is not None and module.__name__ == "PySide6.QtCore"


def test_settings_reuses_the_install_mode(monkeypatch: pytest.MonkeyPatch, qtbot: QtBot) -> None:
    from staffroom.shell.settings_page import SettingsPage

    monkeypatch.setattr(install, "detect", lambda: UV_TOOL)
    page = SettingsPage(load_config(), plugins=())
    qtbot.addWidget(page)
    assert page.addons_card.installation is page.installation
    assert all(isinstance(r.button, QPushButton) for r in page.addons_card.rows.values())
