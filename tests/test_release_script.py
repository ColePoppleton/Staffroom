"""scripts/release.py: changelog rotation, notes extraction, install pins."""

import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release.py"
spec = importlib.util.spec_from_file_location("release", SCRIPT)
assert spec and spec.loader
release = importlib.util.module_from_spec(spec)
sys.modules["release"] = release
spec.loader.exec_module(release)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "0.1.0"\n')
    (tmp_path / "CHANGELOG.md").write_text(
        "# Changelog\n\nintro\n\n## [Unreleased]\n\n### Added\n- thing\n\n"
        "## [0.1.0] - 2026-10-08\n\n- first\n"
    )
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release, "PYPROJECT", tmp_path / "pyproject.toml")
    monkeypatch.setattr(release, "CHANGELOG", tmp_path / "CHANGELOG.md")
    monkeypatch.setattr(release, "README", tmp_path / "README.md")
    monkeypatch.setattr(release, "DOCS", tmp_path / "docs")
    (tmp_path / "docs").mkdir()
    return tmp_path


PIN = "git+https://github.com/ColePoppleton/Staffroom@v"
REAL_ROOT = SCRIPT.parents[1]


def test_bump_rotates_changelog(project: Path) -> None:
    assert release.current_version() == "0.1.0"
    assert release.bump("minor") == "0.2.0"
    body = release.release_changelog("0.2.0")
    assert body == "### Added\n- thing"
    text = (project / "CHANGELOG.md").read_text()
    assert "## [Unreleased]\n\n## [0.2.0] - " in text
    assert text.index("## [0.2.0]") < text.index("## [0.1.0]")
    assert release.notes("0.2.0") == "### Added\n- thing"
    assert release.notes("0.1.0") == "- first"
    with pytest.raises(SystemExit, match="empty"):
        release.release_changelog("0.3.0")


def test_bump_parts(project: Path) -> None:
    assert release.bump("patch") == "0.1.1"
    assert release.bump("major") == "1.0.0"
    with pytest.raises(SystemExit):
        release.bump("huge")


def test_bump_repins_install_lines_and_wheel(project: Path) -> None:
    (project / "README.md").write_text(f"    uv tool install --python 3.12 {PIN}0.1.0\n")
    guide = project / "docs" / "guide"
    guide.mkdir()
    (guide / "install.md").write_text(
        f"uv tool install --python 3.12 {PIN}0.1.0\n"
        "or `uv tool install --python 3.12 ./staffroom-0.1.0-py3-none-any.whl`.\n"
        "Stay on `v0.1.0`? Fine.\n"
    )
    (project / "docs" / "index.md").write_text("no install line here\n")
    audit = project / "docs" / "audits" / "2026-10-01"
    audit.mkdir(parents=True)
    old = f"quoted: {PIN}0.0.9\n"
    (audit / "report.md").write_text(old)
    (project / "docs" / "changelog.md").write_text(old)

    changed = release.pin_install_docs("0.2.0")

    assert sorted(p.relative_to(project).as_posix() for p in changed) == [
        "README.md",
        "docs/guide/install.md",
    ]
    assert (project / "README.md").read_text() == f"    uv tool install --python 3.12 {PIN}0.2.0\n"
    text = (guide / "install.md").read_text()
    assert f"{PIN}0.2.0\n" in text
    assert "./staffroom-0.2.0-py3-none-any.whl" in text
    assert "Stay on `v0.1.0`" in text  # prose is not a pin
    assert (audit / "report.md").read_text() == old  # dated record
    assert (project / "docs" / "changelog.md").read_text() == old  # build copy
    assert release.pin_install_docs("0.2.0") == []  # idempotent


def test_bump_command_repins_in_the_same_step(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / "README.md").write_text(f"{PIN}0.1.0\n")
    release.main(["release.py", "bump", "minor"])
    assert capsys.readouterr().out.strip() == "0.2.0"
    assert (project / "README.md").read_text() == f"{PIN}0.2.0\n"


def test_tag_stages_the_repinned_pages(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (project / "README.md").write_text(f"{PIN}0.1.0\n")
    (project / "docs" / "index.md").write_text(f"{PIN}0.1.0\n")
    (project / "docs" / "other.md").write_text("nothing pinned\n")
    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", lambda args, **_: calls.append(args))
    assert release.tag() == "v0.1.0"
    add = calls[0]
    assert add[:2] == ["git", "add"]
    assert {"pyproject.toml", "CHANGELOG.md", "uv.lock", "README.md", "docs/index.md"} == set(
        add[2:]
    )


def test_bump_on_a_copy_of_the_real_docs_leaves_no_stale_pin(
    project: Path,
) -> None:
    """Every pin tests/test_install_docs.py checks is one bump rewrites."""
    shutil.copy(REAL_ROOT / "README.md", project / "README.md")
    shutil.rmtree(project / "docs")
    shutil.copytree(REAL_ROOT / "docs", project / "docs")
    audits_before = {
        p: p.read_bytes() for p in (project / "docs" / "audits").rglob("*") if p.is_file()
    }

    release.pin_install_docs("98.76.54")

    pin = re.compile(r"Staffroom@v(\d+\.\d+\.\d+)")
    wheel = re.compile(r"staffroom-(\d+\.\d+\.\d+)-py3-none-any\.whl")
    found = {
        (m, page.relative_to(project).as_posix())
        for page in release.install_pages()
        for rx in (pin, wheel)
        for m in rx.findall(page.read_text(encoding="utf-8"))
    }
    names = {name for _, name in found}
    assert {"README.md", "docs/index.md", "docs/guide/install.md"} <= names
    assert {version for version, _ in found} == {"98.76.54"}, sorted(found)
    assert audits_before == {
        p: p.read_bytes() for p in (project / "docs" / "audits").rglob("*") if p.is_file()
    }
