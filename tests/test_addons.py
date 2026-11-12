"""Optional add-ons (#5), the Qt-free part: the catalogue matches the extras
in pyproject.toml, availability is a look at the disk (never an import), the
plan follows how this copy was installed and touches only the running
environment, and a failed change is one sentence, put back when it broke
the copy. No test runs uv: every one passes a fake runner (and the root
conftest makes the real one fail a test)."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Callable, Mapping, Sequence
from importlib import machinery
from pathlib import Path

import pytest

from staffroom.core import addons, install
from staffroom.core.addons import Outcome, Plan
from staffroom.core.install import Installation, InstallKind

ROOT = Path(__file__).resolve().parents[1]
QT_PIN = "==6.12.0.*"


def _pyproject() -> dict[str, object]:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]


def _name(requirement: str) -> tuple[str, str]:
    match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)$", requirement)
    assert match, requirement
    return re.sub(r"[-_.]+", "-", match.group(1)).lower(), match.group(2).strip()


# -- the catalogue -------------------------------------------------------------


def test_every_addon_is_an_extra_with_the_same_wheels() -> None:
    extras = _pyproject()["optional-dependencies"]
    assert isinstance(extras, dict)
    assert set(extras) == set(addons.ADDONS)
    for name, requirements in extras.items():
        wheels = {_name(r)[0] for r in requirements}
        assert wheels == set(addons.ADDONS[name].distributions), name


def test_extras_pin_the_qt_release_of_the_slim_pair() -> None:
    """Every Qt wheel at one release: an Addons or WebEngine wheel from
    another release than Essentials does not install (or crashes)."""
    project = _pyproject()
    slim = {_name(r)[1] for r in project["dependencies"] if _name(r)[0].startswith("pyside6")}
    assert slim == {QT_PIN}
    for requirements in project["optional-dependencies"].values():
        for requirement in requirements:
            assert _name(requirement)[1] == QT_PIN, requirement
    assert QT_PIN.removeprefix("==").removesuffix(".*") == addons.QT_VERSION


def test_the_default_install_has_no_addon() -> None:
    # The dev environment is the slim one (tests/test_qt_modules.py).
    assert addons.installed() == frozenset()
    assert addons.missing(["web"]) == (addons.ADDONS["web"],)


def test_needs_text_and_labels() -> None:
    web, media = addons.ADDONS["web"], addons.ADDONS["media"]
    assert addons.needs_text([web]) == "Needs the Web add-on"
    assert addons.needs_text([web, media]) == "Needs the Web and Media add-ons"
    assert web.label == "the Web add-on"
    assert "MB to download" in web.size_text()


def test_media_comes_with_web() -> None:
    assert addons.included_in("media", {"web", "media"}) == addons.ADDONS["web"]
    assert addons.included_in("media", {"media"}) is None
    assert addons.included_in("web", {"web", "media"}) is None


def test_an_unknown_name_is_missing_and_never_installed() -> None:
    assert not addons.is_installed("teleport")
    (ghost,) = addons.missing(["teleport"])
    assert ghost.name == "teleport"
    assert addons.unknown(["web", "teleport"]) == ["teleport"]


# -- the probe -----------------------------------------------------------------


def _fake_pyside(
    monkeypatch: pytest.MonkeyPatch, folder: Path, modules: list[str], versions: dict[str, str]
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    suffix = machinery.EXTENSION_SUFFIXES[0]
    for module in modules:
        (folder / f"{module}{suffix}").write_bytes(b"")
        (folder / f"{module}.pyi").write_text("")
    monkeypatch.setattr(addons, "_pyside_dirs", lambda: [folder])

    def version(dist: str) -> str:
        if dist not in versions:
            raise addons.PackageNotFoundError(dist)
        return versions[dist]

    monkeypatch.setattr(addons, "version", version)
    addons.refresh()


def test_probe_finds_an_addon_on_disk(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_pyside(
        monkeypatch,
        tmp_path / "PySide6",
        ["QtCore", "QtMultimedia", "QtMultimediaWidgets"],
        {"pyside6-essentials": "6.12.0", "pyside6-addons": "6.12.0"},
    )
    assert addons.is_installed("media")
    assert not addons.is_installed("web")
    assert addons.installed() == {"media"}


def test_probe_ignores_stub_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "PySide6"
    _fake_pyside(monkeypatch, folder, [], {"pyside6-essentials": "6.12.0"})
    (folder / "QtMultimedia.pyi").write_text("")
    (folder / "QtMultimediaWidgets.pyi").write_text("")
    assert not addons.is_installed("media")


def test_probe_refuses_another_qt_release(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_pyside(
        monkeypatch,
        tmp_path / "PySide6",
        ["QtWebEngineCore", "QtWebEngineWidgets"],
        {
            "pyside6-essentials": "6.12.0",
            "pyside6-addons": "6.12.0",
            "pyside6-webengine": "6.11.2.1",
        },
    )
    assert not addons.is_installed("web")


def test_probe_accepts_a_build_number(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _fake_pyside(
        monkeypatch,
        tmp_path / "PySide6",
        ["QtWebEngineCore", "QtWebEngineWidgets"],
        {
            "pyside6-essentials": "6.12.0",
            "pyside6-addons": "6.12.0",
            "pyside6-webengine": "6.12.0.140",
        },
    )
    assert addons.is_installed("web")


def test_the_answer_is_kept_until_refresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "PySide6"
    _fake_pyside(monkeypatch, folder, [], {"pyside6-essentials": "6.12.0"})
    assert not addons.is_installed("media")
    _fake_pyside(monkeypatch, folder, ["QtMultimedia", "QtMultimediaWidgets"], {})
    monkeypatch.setattr(addons, "_pyside_dirs", lambda: [folder])
    addons.is_installed.cache_clear()
    assert addons.is_installed("media")


# -- the plan ------------------------------------------------------------------

UV = "/opt/uv/bin/uv"


def _uv_tool(tmp_path: Path, receipt: str) -> Installation:
    env = tmp_path / "tools" / "staffroom"
    package = env / "lib" / "python3.12" / "site-packages" / "staffroom"
    package.mkdir(parents=True)
    (env / install.UV_RECEIPT).write_text(receipt)
    return Installation(InstallKind.UV_TOOL, package)


RECEIPT = """\
[tool]
requirements = [{ name = "staffroom", git = "https://github.com/ColePoppleton/Staffroom?rev=main" }]
python = "3.12"
entrypoints = [
    { name = "staff", install-path = "/somewhere/bin/staff", from = "staffroom" },
    { name = "staffroom", install-path = "/somewhere/bin/staffroom", from = "staffroom" },
]
"""


def test_a_uv_tool_reinstalls_from_its_own_source_into_its_own_folders(tmp_path: Path) -> None:
    here = _uv_tool(tmp_path, RECEIPT)
    plan = addons.plan({"web"}, here, uv=UV)
    assert plan.runnable and plan.kind is InstallKind.UV_TOOL
    assert plan.command[:3] == (UV, "tool", "install")
    assert plan.command[-1] == (
        "staffroom[web] @ git+https://github.com/ColePoppleton/Staffroom@main"
    )
    assert plan.command[plan.command.index("--python") + 1] == "3.12"
    # Only the environment that is running, and only its own command links.
    assert plan.env == {
        "UV_TOOL_DIR": str(tmp_path / "tools"),
        "UV_TOOL_BIN_DIR": "/somewhere/bin",
    }
    # The shared PySide6 files come back after a wheel leaves.
    for dist in addons.SLIM_DISTRIBUTIONS:
        assert dist in plan.command
    assert "UV_TOOL_DIR=" in plan.line()


def test_removing_the_last_addon_drops_the_extras(tmp_path: Path) -> None:
    here = _uv_tool(tmp_path, RECEIPT)
    assert addons.plan(set(), here, uv=UV).command[-1] == (
        "staffroom @ git+https://github.com/ColePoppleton/Staffroom@main"
    )
    both = addons.plan({"web", "media"}, here, uv=UV).command[-1]
    assert both.startswith("staffroom[media,web] @ ")


@pytest.mark.parametrize(
    ("requirement", "expected"),
    [
        (
            {"name": "staffroom", "git": "https://github.com/ColePoppleton/Staffroom?rev=v0.8.1"},
            "staffroom[web] @ git+https://github.com/ColePoppleton/Staffroom@v0.8.1",
        ),
        (
            {"name": "staffroom", "git": "https://github.com/ColePoppleton/Staffroom"},
            "staffroom[web] @ git+https://github.com/ColePoppleton/Staffroom",
        ),
        (
            {"name": "staffroom", "path": "/w/staffroom-0.9.1-py3-none-any.whl"},
            "staffroom[web] @ file:///w/staffroom-0.9.1-py3-none-any.whl",
        ),
        ({"name": "staffroom", "directory": "/w/src"}, "staffroom[web] @ file:///w/src"),
        ({"name": "staffroom", "specifier": "==0.9.1"}, "staffroom[web]==0.9.1"),
        ({"name": "staffroom"}, "staffroom[web]"),
        ({"name": "staffroom", "editable": "/w/src"}, None),
        ({"git": "https://example.invalid/x"}, None),
    ],
)
def test_requirement_keeps_the_source(
    requirement: Mapping[str, object], expected: str | None
) -> None:
    assert addons.requirement_string(requirement, ["web"]) == expected


def test_a_receipt_it_cannot_read_gives_the_manual_route(tmp_path: Path) -> None:
    here = _uv_tool(tmp_path, "this is not toml [")
    plan = addons.plan({"web"}, here, uv=UV)
    assert not plan.runnable
    assert plan.manual == (
        "uv tool install --python 3.12 "
        "'staffroom[web] @ git+https://github.com/ColePoppleton/Staffroom@main'"
    )
    assert plan.why_manual


def test_other_requirements_stay_with_the_tool(tmp_path: Path) -> None:
    receipt = RECEIPT.replace('rev=main" }]', 'rev=main" }, { name = "rich", specifier = ">=13" }]')
    plan = addons.plan({"media"}, _uv_tool(tmp_path, receipt), uv=UV)
    assert plan.command[plan.command.index("--with") + 1] == "rich>=13"


def test_a_checkout_syncs_with_one_extra_per_addon(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    here = Installation(InstallKind.CHECKOUT, root / "src" / "staffroom", root)
    plan = addons.plan({"web", "media"}, here, uv=UV)
    assert plan.cwd == root
    assert plan.command[:2] == (UV, "sync")
    assert plan.command[2:6] == ("--extra", "media", "--extra", "web")
    assert "--reinstall-package" in plan.command
    assert plan.env == {}
    assert plan.manual == f"cd {root} && uv sync --extra media --extra web"


def test_a_bundle_gets_the_manual_route_not_a_guess(tmp_path: Path) -> None:
    here = Installation(InstallKind.OTHER, tmp_path / "Staffroom.app" / "staffroom")
    plan = addons.plan({"web"}, here, uv=UV)
    assert not plan.runnable
    assert "cannot add to itself" in plan.why_manual
    assert "staffroom[web]" in plan.manual


def test_no_uv_gives_the_manual_route(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(addons, "find_uv", lambda: None)
    plan = addons.plan({"web"}, _uv_tool(tmp_path, RECEIPT))
    assert not plan.runnable
    assert "could not find uv" in plan.why_manual


def test_an_unknown_addon_is_refused(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        addons.plan({"teleport"}, _uv_tool(tmp_path, RECEIPT), uv=UV)


# -- running it ----------------------------------------------------------------


class FakeUv:
    """Answers the commands :func:`addons.apply` runs, in order: the change in
    a throwaway environment and its import check, the change for real and its
    check, then (only when that check fails) putting the old set back and its
    check. Each gets the exit code set for it; every call is recorded with
    its environment."""

    def __init__(
        self,
        install: int = 0,
        verify: int = 0,
        output: str = "",
        restore: int = 0,
        trial: int = 0,
        trial_verify: int = 0,
    ) -> None:
        self.installs = [trial, install, restore]
        self.verifies = [trial_verify, verify, 0]
        self.output = output
        self.calls: list[tuple[str, ...]] = []
        self.envs: list[Mapping[str, str]] = []
        self.done = 0  # installs run so far

    def __call__(
        self,
        command: Sequence[str],
        cwd: Path | None,
        env: Mapping[str, str],
        line: Callable[[str], None],
    ) -> int:
        self.calls.append(tuple(command))
        self.envs.append(dict(env))
        if command[1] == "-c":
            return self.verifies[self.done - 1]
        self.done += 1
        for text in self.output.splitlines():
            line(text)
        return self.installs[self.done - 1]


def _plans(tmp_path: Path, before: set[str], after: set[str]) -> tuple[Plan, Plan]:
    here = _uv_tool(tmp_path, RECEIPT)
    return addons.plan(after, here, uv=UV), addons.plan(before, here, uv=UV)


def test_a_change_that_works_asks_for_a_restart(tmp_path: Path) -> None:
    fake = FakeUv(output="Resolved 40 packages in 1.2s\nInstalled 2 packages in 3s")
    lines: list[str] = []
    steps: list[str] = []
    target, previous = _plans(tmp_path, set(), {"web"})
    outcome = addons.apply(
        target,
        previous,
        runner=fake,
        log_line=lines.append,
        progress=steps.append,
        scratch=tmp_path,
    )
    assert outcome == Outcome(True, "Installed the Web add-on. Restart Staffroom to use it.", True)
    assert lines == ["Resolved 40 packages in 1.2s", "Installed 2 packages in 3s"] * 2
    assert "Resolved 40 packages in 1.2s" in steps and "Checking it works…" in steps
    # Tried, checked, then done for real and checked again.
    assert fake.calls[0] == fake.calls[2] == target.command
    real_verify = fake.calls[3]
    assert "QtPdf" in real_verify[2] and "QtWebEngineWidgets" in real_verify[2]
    assert "PySide6.__file__" in real_verify[2]
    assert fake.envs[2] == target.env


def test_it_is_tried_in_a_throwaway_environment_first(tmp_path: Path) -> None:
    fake = FakeUv()
    target, previous = _plans(tmp_path, set(), {"media"})
    addons.apply(target, previous, runner=fake, scratch=tmp_path)
    trial_env = fake.envs[0]
    trial = Path(trial_env["UV_TOOL_DIR"]).parent
    assert trial.parent == tmp_path and trial.name.startswith("staffroom-addons-")
    assert trial_env["UV_TOOL_BIN_DIR"] == str(trial / "bin")
    # The check runs that environment's own Python, not the running one.
    assert fake.calls[1][0] == str(trial / "tools" / "staffroom" / "bin" / "python")
    assert not trial.exists()  # cleared away afterwards


def test_a_checkout_is_tried_in_another_project_environment(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    here = Installation(InstallKind.CHECKOUT, root / "src" / "staffroom", root)
    test_plan, python = addons.plan({"web"}, here, uv=UV).trial(tmp_path / "t")  # type: ignore[misc]
    assert test_plan.env == {"UV_PROJECT_ENVIRONMENT": str(tmp_path / "t" / "env")}
    assert test_plan.cwd == root
    assert python == tmp_path / "t" / "env" / "bin" / "python"


@pytest.mark.parametrize(
    ("output", "sentence"),
    [
        ("error: Failed to fetch: `https://pypi.org/simple/x/`\n  dns error", addons.NO_NETWORK),
        ("error: request failed: invalid peer certificate: UnknownIssuer", addons.BLOCKED),
        ("error: HTTP status client error (407 Proxy Authentication Required)", addons.BLOCKED),
        ("Caused by: tunnel error: failed to create underlying connection", addons.BLOCKED),
        ("hint: Packages were unavailable because the network was disabled", addons.NO_NETWORK),
        ("error: No space left on device (os error 28)", addons.NO_SPACE),
        ("error: operation timed out", addons.TOO_SLOW),
        ("error: something nobody has seen", addons.FAILED),
    ],
)
def test_a_failed_download_is_one_sentence(tmp_path: Path, output: str, sentence: str) -> None:
    fake = FakeUv(trial=2, output=output)
    outcome = addons.apply(*_plans(tmp_path, set(), {"web"}), runner=fake, scratch=tmp_path)
    assert outcome == Outcome(False, sentence)
    # Only the throwaway environment was tried: the copy was never touched.
    assert len(fake.calls) == 1 and "staffroom-addons-" in fake.envs[0]["UV_TOOL_DIR"]
    assert "\n" not in outcome.message and "Traceback" not in outcome.message


def test_a_change_that_does_not_import_in_the_trial_changes_nothing(tmp_path: Path) -> None:
    fake = FakeUv(trial_verify=1)
    outcome = addons.apply(*_plans(tmp_path, set(), {"web"}), runner=fake, scratch=tmp_path)
    assert outcome == Outcome(False, addons.WOULD_BREAK)
    assert len(fake.calls) == 2  # the trial and its check; no real change


def test_a_change_that_breaks_the_copy_is_put_back(tmp_path: Path) -> None:
    fake = FakeUv(verify=1)
    target, previous = _plans(tmp_path, {"media"}, {"media", "web"})
    outcome = addons.apply(target, previous, runner=fake, scratch=tmp_path)
    assert outcome == Outcome(False, addons.BROKEN, restart=True)
    assert fake.calls[4] == previous.command  # the old set, from the cache
    assert fake.envs[4] == previous.env


def test_a_copy_that_cannot_be_put_back_gets_the_repair_line(tmp_path: Path) -> None:
    fake = FakeUv(verify=1, restore=1)
    target, previous = _plans(tmp_path, set(), {"web"})
    outcome = addons.apply(target, previous, runner=fake, scratch=tmp_path)
    assert not outcome.ok and outcome.message == addons.STUCK
    assert outcome.command == previous.line()


def test_uv_that_cannot_start_points_at_the_line(tmp_path: Path) -> None:
    fake = FakeUv(trial=127)
    target, previous = _plans(tmp_path, set(), {"media"})
    outcome = addons.apply(target, previous, runner=fake, scratch=tmp_path)
    assert outcome.message == addons.NO_UV
    assert outcome.command == target.manual


def test_a_manual_plan_runs_nothing(tmp_path: Path) -> None:
    here = Installation(InstallKind.OTHER, tmp_path / "x" / "staffroom")
    fake = FakeUv()
    outcome = addons.apply(
        addons.plan({"web"}, here, uv=UV), addons.plan(set(), here, uv=UV), runner=fake
    )
    assert not outcome.ok and outcome.command and fake.calls == []


def test_change_text() -> None:
    none: frozenset[str] = frozenset()
    assert addons.change_text(none, frozenset({"media"})) == (
        "Installed the Media add-on. Restart Staffroom to use it."
    )
    assert addons.change_text(frozenset({"web"}), none) == (
        "Removed the Web add-on. Restart Staffroom to use it."
    )


def test_the_real_runner_reports_a_missing_program(tmp_path: Path) -> None:
    # Not uv: a program that does not exist, so nothing is ever installed.
    lines: list[str] = []
    code = addons.real_run_command(["/nonexistent/uv-not-here"], tmp_path, {}, lines.append)
    assert code == 127 and lines


def test_the_real_runner_streams_lines(tmp_path: Path) -> None:
    lines: list[str] = []
    code = addons.real_run_command(
        ["/bin/sh", "-c", "echo one; echo two >&2; exit 3"], tmp_path, {}, lines.append
    )
    assert code == 3 and lines == ["one", "two"]


def test_a_checkout_update_keeps_the_addons(monkeypatch: pytest.MonkeyPatch) -> None:
    """``staff update`` syncs with an ``--extra`` per add-on installed: a
    plain ``uv sync`` would remove them, and the files the Qt wheels share."""
    from staffroom.core import update

    monkeypatch.setattr(addons, "is_installed", lambda name: name == "web")
    assert update._kept_extras() == ["--extra", "web"]
