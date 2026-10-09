"""The docs home page (#90) shows real outputs and makes privacy claims that
must stay true.

* Every picture on the home page is a file in docs/ that
  ``scripts/screenshots.sh`` writes, so ``just screenshots`` regenerates it
  from the example files (never the owner's own).
* Every claim in the privacy strip is backed by a sentence on the Privacy
  page; if either side is reworded, this test says which pair drifted.
* The links into the Privacy page land on headings that exist.
* Teachers' pages come first in the nav; the contributor pages sit under one
  Contributing section at the end.
"""

import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
INDEX = DOCS / "index.md"
PRIVACY = DOCS / "guide" / "privacy.md"
SCREENSHOTS = ROOT / "scripts" / "screenshots.sh"

# Strip claim on the home page -> the sentence on the Privacy page it rests on.
CLAIMS = {
    "Stored, on this Mac only": "Nothing leaves the machine.",
    "under `~/.config/staffroom/`": "`~/.config/staffroom/config.toml`",
    "an index of the files (and their text) in your resources folder": (
        "plus the text of `.py`, `.txt`, `.md`, `.csv` and `.pdf` files"
    ),
    "run counts per tool": "run count (launcher and `staff` commands",
    "a log of file paths": "the **paths** of files read, written, copied or promoted",
    "identifier columns are dropped on load": "is **dropped on load**",
    "only class-level aggregates are saved": "Only aggregates are ever written",
    "No log holds a value from your files.": "neither holds a value from your files",
    "No account and no server": "There is no account and no server",
    "the only network call is the update check, when the app runs from a git checkout": (
        "The app checks its git remote for updates when started from a checkout, "
        "and that is the only network call it makes."
    ),
    "Removing every trace is deleting a short list of folders.": (
        "removing the app's traces is a\nmatter of deleting folders"
    ),
}

CONTRIBUTOR_PAGES = ["process.md", "adding-a-tool.md", "ROADMAP.md", "PHASES.md", "audits/"]


def _flat(text: str) -> str:
    return " ".join(text.split())


def _slug(heading: str) -> str:
    """Python-Markdown's toc slugify, the one MkDocs uses for anchors."""
    value = unicodedata.normalize("NFKD", heading).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def test_every_home_page_image_is_made_by_the_screenshot_script() -> None:
    page = INDEX.read_text(encoding="utf-8")
    script = SCREENSHOTS.read_text(encoding="utf-8")
    images = re.findall(r"!\[[^\]]*\]\(([^)\s]+\.png)\)", page)
    assert len(images) >= 3, "the home page should show real output pages"
    for image in images:
        assert (DOCS / image).is_file(), f"docs/{image} is missing"
        assert Path(image).stem in script, f"scripts/screenshots.sh does not write {image}"
    for snippet in re.findall(r'--8<-- "([^"]+)"', page):
        assert (DOCS / snippet).is_file(), f"docs/{snippet} is missing"
        assert f"docs/{snippet}" in script, f"scripts/screenshots.sh does not write {snippet}"


def test_privacy_strip_claims_match_the_privacy_page() -> None:
    page = _flat(INDEX.read_text(encoding="utf-8"))
    privacy = _flat(PRIVACY.read_text(encoding="utf-8"))
    for claim, source in CLAIMS.items():
        assert _flat(claim) in page, f"home page no longer says: {claim!r}"
        assert _flat(source) in privacy, (
            f"guide/privacy.md no longer says {source!r}, which backs the home page's "
            f"claim {claim!r}: update both together"
        )


def test_home_page_links_into_privacy_land_on_headings() -> None:
    page = INDEX.read_text(encoding="utf-8")
    headings = {
        _slug(line.lstrip("#").strip())
        for line in PRIVACY.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    }
    anchors = re.findall(r"\(guide/privacy\.md#([\w-]+)\)", page)
    assert anchors, "the privacy strip should link into the Privacy page"
    for anchor in anchors:
        assert anchor in headings, f"guide/privacy.md has no heading for #{anchor}"


def test_contributor_pages_are_under_contributing_at_the_end_of_the_nav() -> None:
    text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    nav = text[text.index("\nnav:\n") :].splitlines()[1:]
    top = [line for line in nav if re.match(r"^  - ", line)]
    assert top[-1].strip() == "- Contributing:", f"Contributing should be last, not {top[-1]}"
    start = nav.index("  - Contributing:")
    teacher, contributing = "\n".join(nav[:start]), "\n".join(nav[start:])
    for page in CONTRIBUTOR_PAGES:
        assert page in contributing, f"{page} should be under Contributing"
        assert page not in teacher, f"{page} is in the teachers' part of the nav"
