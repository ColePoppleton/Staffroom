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


LINE = "uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@main"
WHEEL_LINE = "uv tool install --python 3.12 ./staffroom-{}-py3-none-any.whl"
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


def test_bump_repins_the_wheel_and_leaves_the_main_line_alone(project: Path) -> None:
    """The git line follows @main since #11, so ``uv tool upgrade`` updates a
    copy; only the wheel filename carries a version (#100)."""
    (project / "README.md").write_text(f"    {LINE}\n")
    guide = project / "docs" / "guide"
    guide.mkdir()
    (guide / "install.md").write_text(
        f"{LINE}\nor `{WHEEL_LINE.format('0.1.0')}`.\nStay on `v0.1.0`? Fine.\n"
    )
    (project / "docs" / "index.md").write_text("no install line here\n")
    audit = project / "docs" / "audits" / "2026-10-01"
    audit.mkdir(parents=True)
    old = f"quoted: {WHEEL_LINE.format('0.0.9')}\n"
    (audit / "report.md").write_text(old)
    (project / "docs" / "changelog.md").write_text(old)

    changed = release.pin_install_docs("0.2.0")

    assert [p.relative_to(project).as_posix() for p in changed] == ["docs/guide/install.md"]
    assert (project / "README.md").read_text() == f"    {LINE}\n"  # @main untouched
    text = (guide / "install.md").read_text()
    assert f"{LINE}\n" in text
    assert WHEEL_LINE.format("0.2.0") in text
    assert "Stay on `v0.1.0`" in text  # prose is not a pin
    assert (audit / "report.md").read_text() == old  # dated record
    assert (project / "docs" / "changelog.md").read_text() == old  # build copy
    assert release.pin_install_docs("0.2.0") == []  # idempotent


def test_bump_command_repins_in_the_same_step(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (project / "README.md").write_text(f"{LINE}\n{WHEEL_LINE.format('0.1.0')}\n")
    release.main(["release.py", "bump", "minor"])
    assert capsys.readouterr().out.strip() == "0.2.0"
    assert (project / "README.md").read_text() == f"{LINE}\n{WHEEL_LINE.format('0.2.0')}\n"


def test_tag_stages_the_repinned_pages(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (project / "README.md").write_text(f"{WHEEL_LINE.format('0.1.0')}\n")
    (project / "docs" / "index.md").write_text(f"{WHEEL_LINE.format('0.1.0')}\n")
    (project / "docs" / "other.md").write_text(f"{LINE}\n")  # nothing to re-pin
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
    """Every wheel tests/test_install_docs.py checks is one bump rewrites, and
    the @main lines come through unchanged."""
    shutil.copy(REAL_ROOT / "README.md", project / "README.md")
    shutil.rmtree(project / "docs")
    shutil.copytree(REAL_ROOT / "docs", project / "docs")
    audits_before = {
        p: p.read_bytes() for p in (project / "docs" / "audits").rglob("*") if p.is_file()
    }
    main_lines_before = {
        page: page.read_text(encoding="utf-8").count("Staffroom@main")
        for page in release.install_pages()
    }

    release.pin_install_docs("98.76.54")

    wheel = re.compile(r"staffroom-(\d+\.\d+\.\d+)-py3-none-any\.whl")
    found = {
        (m, page.relative_to(project).as_posix())
        for page in release.install_pages()
        for m in wheel.findall(page.read_text(encoding="utf-8"))
    }
    assert "docs/guide/install.md" in {name for _, name in found}
    assert {version for version, _ in found} == {"98.76.54"}, sorted(found)
    assert not any(
        re.search(r"Staffroom@v\d", page.read_text(encoding="utf-8"))
        for page in release.install_pages()
    )
    assert main_lines_before == {
        page: page.read_text(encoding="utf-8").count("Staffroom@main")
        for page in release.install_pages()
    }
    assert sum(main_lines_before.values()) >= 3  # README, home page, Install
    assert audits_before == {
        p: p.read_bytes() for p in (project / "docs" / "audits").rglob("*") if p.is_file()
    }
