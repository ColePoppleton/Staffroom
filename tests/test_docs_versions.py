"""The public docs state one version, the current one (#14).

A page that says "the latest release is v0.6.0" above a line that installs
v0.8.1 tells a colleague the rest may be wrong too. Prose describes versions
in words (*the newer release's number*); the only version number on a page
is the pinned wheel filename, which ``scripts/release.py`` rewrites on every
release and ``tests/test_install_docs.py`` holds to pyproject.toml. The
changelog page (built from CHANGELOG.md) and the dated audits are history and
are not checked.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SKIP = {DOCS / "changelog.md"}
SKIP_DIRS = {DOCS / "audits"}

# Ways a page names a release: v1.2.3, staffroom-1.2.3 (a wheel), "Staffroom
# 1.2.3", "1.2.3 out" (the sidebar's words), "before 1.2" / "since v1.2".
# Bare dotted numbers are left alone: they are spec references (1.2.4).
VERSION = re.compile(
    r"(?:\bv|\bstaffroom-|\bStaffroom )(?P<a>\d+\.\d+\.\d+)\b"
    r"|\b(?P<b>\d+\.\d+(?:\.\d+)?) out\b"
    r"|\b(?:before|since|after|from|until) v?(?P<c>\d+\.\d+(?:\.\d+)?)\b",
)


def _current() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def _pages() -> list[Path]:
    pages = [ROOT / "README.md"]
    for path in sorted(DOCS.rglob("*.md")):
        if path in SKIP or any(d in path.parents for d in SKIP_DIRS):
            continue
        pages.append(path)
    return pages


def _versions(text: str) -> list[str]:
    return [next(v for v in m.groups() if v) for m in VERSION.finditer(text)]


def test_pattern_finds_the_ways_a_page_names_a_release() -> None:
    text = (
        "the latest release, **v0.6.0**; `./staffroom-0.8.1-py3-none-any.whl`; "
        "Running Staffroom 0.5.0; reads `v0.8.1 · 0.9.0 out`; Installed before 0.9; "
        "spec 1.2.4 and 3.3.2; Python 3.12; vX.Y.Z"
    )
    assert _versions(text) == ["0.6.0", "0.8.1", "0.5.0", "0.8.1", "0.9.0", "0.9"]


def test_no_docs_page_names_a_version_but_the_current_one() -> None:
    current = _current()
    stale = []
    for page in _pages():
        for version in _versions(page.read_text(encoding="utf-8")):
            if version != current:
                stale.append(f"{page.relative_to(ROOT)}: {version}")
    assert not stale, (
        f"pages name a version other than {current} (describe it in words, or let "
        "scripts/release.py pin it): " + ", ".join(stale)
    )
