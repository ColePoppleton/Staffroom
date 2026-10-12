"""scripts/release.py: changelog rotation, the release notes, the changelog rules,
install pins."""

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
        "# Changelog\n\nintro\n\n## [Unreleased]\n\n"
        "Sheets print faster. Nothing else changes.\n\n### Added\n- thing\n\n"
        "## [0.1.0] - 2026-10-08\n\nThe first release. It has one tool.\n\n### Added\n- first\n"
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
    assert body == "Sheets print faster. Nothing else changes.\n\n### Added\n- thing"
    text = (project / "CHANGELOG.md").read_text()
    assert "## [Unreleased]\n\n## [0.2.0] - " in text
    assert text.index("## [0.2.0]") < text.index("## [0.1.0]")
    assert release.notes("0.2.0").startswith("Sheets print faster. Nothing else changes.\n\n")
    assert "- first\n" in release.notes("0.1.0")
    with pytest.raises(SystemExit, match="empty"):
        release.release_changelog("0.3.0")


def test_bump_refuses_an_unreleased_section_without_a_teacher_summary(project: Path) -> None:
    changelog = project / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text().replace("Sheets print faster. Nothing else changes.\n\n", "")
    )
    with pytest.raises(SystemExit, match="two or three sentences for teachers"):
        release.release_changelog("0.2.0")
    assert "## [0.2.0]" not in changelog.read_text()  # nothing rotated


def test_bump_parts(project: Path) -> None:
    assert release.bump("patch") == "0.1.1"
    assert release.bump("major") == "1.0.0"
    with pytest.raises(SystemExit):
        release.bump("huge")


def test_bump_repins_the_wheel_and_leaves_the_main_line_alone(project: Path) -> None:
    """The git line follows @main, so ``uv tool upgrade`` updates a copy; only
    the wheel filename carries a version."""
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


# The release notes and the changelog rules ---------------------------------

SECTION = """## [{version}] - 2026-10-11

{summary}

### Added
- The Library has a **Tags** filter beside *All types*. It lists the tags on
  the files shown, each with how many carry it{ref}.
- Quiz shows the taught log only in retrieval mode.

### Fixed
- Saving settings can no longer leave `config.toml`
  truncated.
"""
SUMMARY = (
    "Options forms only ask what matters, and the Library finds files by tag.\n"
    "Bugs sheets mix crashes with programs that run but print the wrong thing."
)


def changelog(version: str = "0.8.0", summary: str = SUMMARY, ref: str = "") -> str:
    return "# Changelog\n\n## [Unreleased]\n\n" + SECTION.format(
        version=version, summary=summary, ref=ref
    )


def test_notes_lead_with_teachers_then_the_command_then_the_folded_detail(
    project: Path,
) -> None:
    (project / "CHANGELOG.md").write_text(changelog())
    notes = release.notes("0.8.0")
    teachers, update, contributors = notes.split("\n\n", 2)
    # One line each: a Release renders every newline in its body as a break.
    assert teachers == SUMMARY.replace("\n", " ")
    assert update == release.UPDATE_LINE
    assert "`uv tool upgrade staffroom`" in update
    assert contributors.startswith(
        "<details>\n<summary>For contributors: the full list (3 changes)</summary>\n\n### Added\n"
    )
    assert contributors.endswith("\n\n</details>\n")
    assert (
        "- The Library has a **Tags** filter beside *All types*. It lists the tags on "
        "the files shown, each with how many carry it.\n"
    ) in contributors
    assert "- Saving settings can no longer leave `config.toml` truncated.\n" in contributors
    assert release.notes("0.8.0") == notes  # the same section gives the same body


def test_notes_need_a_summary(project: Path) -> None:
    (project / "CHANGELOG.md").write_text(changelog().replace(SUMMARY + "\n\n", ""))
    with pytest.raises(SystemExit, match="no summary for teachers"):
        release.notes("0.8.0")
    with pytest.raises(SystemExit, match=r"no changelog section for 9\.9\.9"):
        release.notes("9.9.9")


def test_unwrap_keeps_blocks_and_fenced_code() -> None:
    text = "Para one\nwraps.\n\n### Added\n- item\n  <file> wraps\n- next\n\n```\nkeep\nthis\n```"
    assert release.unwrap(text) == (
        "Para one wraps.\n\n### Added\n- item <file> wraps\n- next\n\n```\nkeep\nthis\n```"
    )


@pytest.mark.parametrize("ref", [" (#123)", " (see #16)", ", as #43 did"])
def test_a_private_issue_number_in_a_released_section_is_refused(ref: str) -> None:
    problems = release.changelog_problems(changelog("0.4.0", ref=ref))
    assert len(problems) == 1
    assert problems[0].startswith("[0.4.0] cites #")
    assert "private repository" in problems[0]


def test_issue_numbers_after_the_last_private_release_are_this_repositorys() -> None:
    later = "0.9.0"
    assert release.version_key(later) > release.version_key(release.LAST_PRIVATE)
    assert release.changelog_problems(changelog(later, ref=" (#10)")) == []
    # Anchors, headings and entities are not issue numbers.
    assert not release.ISSUE_REF.search("see privacy.md#where-things-live, ### Added, &#123;")


@pytest.mark.parametrize(
    ("summary", "complaint"),
    [
        ("", "no summary paragraph"),
        ("- Tags filter\n- Settings are safer", "is a list"),
        ("Tags filter in the Library.", "has 1 sentences"),
        ("One. Two. Three. Four.", "has 4 sentences"),
        ("Quiz is better (#123). Bugs too.", "cites an issue number"),
        ("Phase 9 is done. The audit found it.", "how the work was organised"),
    ],
)
def test_a_released_section_needs_a_plain_teacher_summary(summary: str, complaint: str) -> None:
    text = changelog(summary=summary).replace("\n\n\n", "\n\n")
    problems = release.changelog_problems(text)
    assert any(complaint in p for p in problems), problems


def test_a_released_section_groups_its_detail(project: Path) -> None:
    text = changelog().replace("### Fixed", "### Phase 7 — polish")
    assert release.changelog_problems(text) == [
        "[0.8.0] heading '### Phase 7 — polish' is not Added/Changed/Fixed",
        "[0.8.0] mentions 'Phase 7' (how the work was organised)",
    ]


def test_check_command(project: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (project / "CHANGELOG.md").write_text(changelog())
    with pytest.raises(SystemExit) as ok:
        release.main(["release.py", "check"])
    assert ok.value.code == 0
    (project / "CHANGELOG.md").write_text(changelog(ref=" (#123)"))
    with pytest.raises(SystemExit) as bad:
        release.main(["release.py", "check"])
    assert bad.value.code == 1
    assert "[0.8.0] cites #123" in capsys.readouterr().out


def test_the_real_changelog_follows_the_rules() -> None:
    """Every released version opens with two or three sentences for teachers,
    groups its detail under Added / Changed / Fixed, and, up to the last
    private release, cites no issue number: those numbers belong to the
    private repository and would open unrelated issues here."""
    text = (REAL_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert release.changelog_problems(text) == []
    released = release.sections(text)
    assert release.LAST_PRIVATE in released
    assert {"0.1.0", "0.2.0", "0.8.0", "0.8.1"} <= set(released)


def test_the_real_release_notes_have_no_hard_wraps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(release, "CHANGELOG", REAL_ROOT / "CHANGELOG.md")
    for version in release.sections(release.CHANGELOG.read_text(encoding="utf-8")):
        notes = release.notes(version)
        for line in notes.splitlines():
            # Every line of prose starts a block: an item, a heading, a tag.
            assert not line.startswith(" "), (version, line)
        assert notes.count("<details>") == notes.count("</details>") == 1


def test_the_site_page_leads_each_version_with_its_summary_and_folds_the_rest() -> None:
    text = changelog() + "\n## [0.1.0] - 2026-10-08\n\nFirst. Second.\n\n### Added\n- one\n"
    text = text.replace("## [Unreleased]\n\n", "## [Unreleased]\n\n### Fixed\n- soon\n\n")
    page = release.site_page(text)
    assert page.startswith('# Changelog\n\n## [Unreleased]\n\n<details markdown="1">\n')
    assert "<summary>Not released yet (1 change)</summary>\n\n**Fixed**\n\n- soon\n\n" in page
    assert (
        '## [0.8.0] - 2026-10-11\n\n<div class="release-summary" markdown="1">\n\n'
        f"{SUMMARY}\n\n</div>\n\n"
        '<details markdown="1">\n<summary>For contributors: the full list (3 changes)</summary>'
    ) in page
    assert page.endswith("**Added**\n\n- one\n\n</details>\n")
    # Nothing is lost: every line of the changelog is on the page, and the
    # groups are labels, so the contents list is one line per version.
    assert all(line.removeprefix("### ") in page for line in text.splitlines())
    assert re.findall(r"^#+ .*$", page, re.M) == [
        "# Changelog",
        "## [Unreleased]",
        "## [0.8.0] - 2026-10-11",
        "## [0.1.0] - 2026-10-08",
    ]


def test_the_real_site_page_builds_from_the_changelog() -> None:
    text = (REAL_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    page = release.site_page(text)
    released = release.sections(text)
    assert page.count('<div class="release-summary"') == len(released)
    assert page.count("<details") == page.count("</details>") == len(released) + 1
