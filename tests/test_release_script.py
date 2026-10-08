"""scripts/release.py: changelog rotation and notes extraction."""

import importlib.util
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
    return tmp_path


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
