"""The README is the repository's front page, written for a teacher (#13).

* Every picture is one the docs site already uses, written by
  ``scripts/screenshots.sh`` from the example files, so ``just screenshots``
  keeps it current and there is no second image pipeline.
* The privacy sentences reuse the home page's wording, which
  ``tests/test_docs_landing.py`` checks against the Privacy page.
* Every tool page in the docs is linked, and the README links the docs site,
  the contributing guide and the licence.
* No developer command remains: those live in the contributing guide.

The install line itself is checked by ``tests/test_install_docs.py``.
"""

import re
from pathlib import Path

from tests.test_docs_landing import CLAIMS

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DOCS = ROOT / "docs"
SITE = "https://colepoppleton.github.io/Staffroom/"

# Claims from the home page's privacy strip that the README repeats word for word.
README_CLAIMS = [
    "run counts per tool",
    "a log of file paths",
    "an index of the files (and their text) in your resources folder",
    "identifier columns are dropped on load",
    "only class-level aggregates are saved",
    "the only network call asks GitHub which release is newest",
]

# Words for the person building Staffroom, not the teacher reading about it.
DEVELOPER = re.compile(
    r"^\s*(?:just|uv run|uv sync|git clone|pytest|pre-commit)\b|PySide6|\bplugin|\bQt\b",
    re.IGNORECASE | re.MULTILINE,
)


def _text() -> str:
    return README.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    return " ".join(text.split())


def test_readme_pictures_are_the_docs_sites_own_renders() -> None:
    text = _text()
    script = (ROOT / "scripts" / "screenshots.sh").read_text(encoding="utf-8")
    images = re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", text) + re.findall(
        r'<img\s[^>]*src="([^"]+)"', text
    )
    assert any("output-" in image for image in images), "show real output pages"
    assert len(images) >= 3
    for image in images:
        assert image.startswith("docs/"), f"{image}: use a relative path into docs/"
        assert (ROOT / image).is_file(), f"{image} is missing"
        assert Path(image).stem in script, f"scripts/screenshots.sh does not write {image}"


def test_readme_privacy_wording_is_the_home_pages_tested_wording() -> None:
    text = _flat(_text())
    for claim in README_CLAIMS:
        assert claim in CLAIMS, f"{claim!r} is not a claim test_docs_landing.py checks"
        assert _flat(claim) in text, f"README no longer says: {claim!r}"
    assert f"{SITE}guide/privacy/" in text


def test_readme_links_every_tool_page_the_docs_and_the_licence() -> None:
    text = _text()
    for page in sorted((DOCS / "tools").glob("*.md")):
        assert f"{SITE}tools/{page.stem}/" in text, f"README does not link tools/{page.stem}"
    assert f"{SITE}contributing/" in text
    assert f"({SITE})" in text, "link the documentation site"
    assert "(LICENSE)" in text and "MIT" in text
    assert "never attach a real marks file" in _flat(text)


def test_readme_has_no_developer_commands() -> None:
    found = [match.group(0).strip() for match in DEVELOPER.finditer(_text())]
    assert not found, f"move these to docs/contributing.md: {found}"
