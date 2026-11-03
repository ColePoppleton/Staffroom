"""``staff addons`` (#5): the same installer as Settings > Add-ons, from a
Terminal. ``addons.change`` is a fake here: nothing is downloaded."""

from __future__ import annotations

from typing import Any

import pytest
from typer.testing import CliRunner

import staffroom.cli
from staffroom.cli import app
from staffroom.core import addons
from staffroom.core.addons import Outcome

runner = CliRunner()


class FakeChange:
    def __init__(self, outcome: Outcome) -> None:
        self.outcome = outcome
        self.asked: list[frozenset[str]] = []

    def __call__(self, wanted: frozenset[str], **kwargs: Any) -> Outcome:
        self.asked.append(frozenset(wanted))
        kwargs["log_line"]("Resolved 3 packages")
        return self.outcome


def test_list_says_what_each_addon_is_for() -> None:
    result = runner.invoke(app, ["addons", "list"])
    assert result.exit_code == 0, result.output
    assert "web    not installed" in result.output
    assert "media  not installed" in result.output
    assert "staff addons install <name>" in result.output


def test_install_runs_the_installer(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeChange(Outcome(True, "Installed the Media add-on. Restart Staffroom to use it."))
    monkeypatch.setattr(addons, "change", fake)
    result = runner.invoke(app, ["addons", "install", "media"])
    assert result.exit_code == 0, result.output
    assert fake.asked == [frozenset({"media"})]
    assert "Installed the Media add-on" in result.output


def test_a_failed_install_is_one_sentence_and_the_line(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeChange(Outcome(False, addons.NO_UV, command="uv tool install x"))
    monkeypatch.setattr(addons, "change", fake)
    result = runner.invoke(app, ["addons", "install", "web"])
    assert result.exit_code == 1
    assert addons.NO_UV in result.output and "uv tool install x" in result.output
    assert "Traceback" not in result.output


def test_an_unknown_addon_names_the_real_ones() -> None:
    result = runner.invoke(app, ["addons", "install", "teleport"])
    assert result.exit_code == 2
    assert "the add-ons are: web, media" in result.output


def test_removing_one_that_is_not_there_does_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeChange(Outcome(True, "x"))
    monkeypatch.setattr(addons, "change", fake)
    result = runner.invoke(app, ["addons", "remove", "media"])
    assert result.exit_code == 0
    assert "The Media add-on is not installed." in result.output
    assert fake.asked == []


def test_media_is_removed_with_web(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeChange(Outcome(True, "x"))
    monkeypatch.setattr(addons, "change", fake)
    monkeypatch.setattr(addons, "installed", lambda: frozenset({"web", "media"}))
    result = runner.invoke(app, ["addons", "remove", "media"])
    assert "comes with the Web add-on" in result.output
    assert fake.asked == []
    runner.invoke(app, ["addons", "remove", "web"])
    assert fake.asked == [frozenset({"media"})]


def test_list_marks_a_tool_whose_addon_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    hello = staffroom.cli.discover_plugins()[-1]

    class Needy:
        name = "webpage"
        description = "Shows a web page."
        version = "0.1.0"
        requires = ("web",)

    monkeypatch.setattr(staffroom.cli, "discover_plugins", lambda: (hello, Needy()))
    result = runner.invoke(app, ["list"])
    assert result.exit_code == 0, result.output
    line = next(x for x in result.output.splitlines() if x.startswith("webpage"))
    assert line.endswith("[needs the web add-on]")
    assert "staff addons install <name>" in result.output
