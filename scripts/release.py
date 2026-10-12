"""Release helper: Keep a Changelog + semantic versioning + git tags.

    uv run python scripts/release.py version              # print the current version
    uv run python scripts/release.py bump patch|minor|major
    uv run python scripts/release.py notes 0.2.0          # that version's GitHub Release body
    uv run python scripts/release.py check                # CHANGELOG.md follows the rules below
    uv run python scripts/release.py site > docs/changelog.md   # the docs site's Changelog page
    uv run python scripts/release.py tag                  # commit the bump and tag it

``just release <part>`` runs bump, lock, tag and push. The tag triggers
.github/workflows/release.yml, which builds the wheel and sdist and creates
the GitHub Release with the notes.

Each version in CHANGELOG.md opens with two or three plain sentences for a
teacher (what they can now do, or what no longer goes wrong), then the
detail grouped under ``### Added`` / ``### Changed`` / ``### Fixed``. Write
the sentences at the top of ``## [Unreleased]`` before releasing; ``bump``
refuses without them. ``notes`` turns a section into the Release body: the
sentences, the update command, and the detail folded under *For
contributors*, with hard-wrapped lines joined (a Release renders every
newline as a line break).

Versions up to ``LAST_PRIVATE`` were built in a private repository whose
issue numbers mean something else here, so their sections cite none.
Later sections may cite this repository's issues; a summary never does.

``bump`` also re-pins the wheel filename the Install guide names
(``staffroom-X.Y.Z-py3-none-any.whl``) in README.md and docs/ to the new
version, so the release commit never points colleagues at the previous
wheel. The git install line follows ``@main`` (so ``uv tool upgrade
staffroom`` updates a copy) and is left alone.
"""

from __future__ import annotations

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"
DOCS = ROOT / "docs"
UNRELEASED = "## [Unreleased]"
SITE = "https://colepoppleton.github.io/Staffroom"

#: The last version released from the private repository. Its issue
#: numbers would open unrelated issues here.
LAST_PRIVATE = "0.8.1"

#: An issue or pull request number, ``#123``; not a heading, an anchor
#: (``page.md#part``) or an HTML entity (``&#123;``).
ISSUE_REF = re.compile(r"(?<![\w/&#])#\d+\b")

#: How the work was organised, which the public notes leave out.
PROCESS_WORDS = re.compile(
    r"\bphase \d|\baudit(?:ed|s)?\b|issues board|/next-task|/merge-prs|\broadmap\b", re.I
)

SECTION = re.compile(r"^## \[([^\]]+)\][^\n]*\n(.*?)(?=^## |\Z)", re.M | re.S)
SENTENCE_END = re.compile(r"[.!?][\"')*_]*(?=\s|$)")

UPDATE_LINE = (
    "**Update:** quit Staffroom, run `uv tool upgrade staffroom` in Terminal, and open it "
    f"again ([Updating]({SITE}/guide/updating/) covers a copy installed from a release tag). "
    f"New to Staffroom? Start with [Install]({SITE}/guide/install/)."
)

# The wheel the Install guide names. Same shape as tests/test_install_docs.py
# checks. The git line installs from @main and has no version to pin.
WHEEL = re.compile(r"(staffroom-)\d+\.\d+\.\d+(-py3-none-any\.whl)")


def current_version() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', PYPROJECT.read_text(), re.M)
    if not m:
        raise SystemExit("no version in pyproject.toml")
    return m.group(1)


def bump(part: str) -> str:
    major, minor, patch = (int(x) for x in current_version().split("-")[0].split("."))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    elif part == "patch":
        patch += 1
    else:
        raise SystemExit("bump takes major, minor or patch")
    new = f"{major}.{minor}.{patch}"
    text = re.sub(
        r'^version\s*=\s*"[^"]+"', f'version = "{new}"', PYPROJECT.read_text(), count=1, flags=re.M
    )
    PYPROJECT.write_text(text)
    return new


def release_changelog(version: str) -> str:
    """Turn the Unreleased section into ``[version] - date`` and open a fresh
    Unreleased above it. Returns the released notes."""
    text = CHANGELOG.read_text()
    if UNRELEASED not in text:
        raise SystemExit(f"CHANGELOG.md has no '{UNRELEASED}' section")
    head, _, rest = text.partition(UNRELEASED)
    m = re.search(r"^## ", rest, re.M)
    body = rest[: m.start()] if m else rest
    tail = rest[m.start() :] if m else ""
    if not body.strip():
        raise SystemExit("the Unreleased section is empty; add changelog lines first")
    problems = summary_problems(split_section(body)[0])
    if problems:
        raise SystemExit(
            "write two or three sentences for teachers at the top of Unreleased first: "
            + "; ".join(problems)
        )
    today = dt.date.today().isoformat()
    new = (
        f"{head}{UNRELEASED}\n\n## [{version}] - {today}\n{body.strip()}\n\n{tail}".rstrip() + "\n"
    )
    CHANGELOG.write_text(new)
    return body.strip()


def install_pages() -> list[Path]:
    """README.md and every page under docs/ a colleague reads to install.

    Audits are dated records that quote old lines on purpose, and
    docs/changelog.md is a git-ignored build-time copy of CHANGELOG.md.
    """
    skip_dir = DOCS / "audits"
    pages = [README] if README.exists() else []
    for path in sorted(DOCS.rglob("*.md")):
        if path == DOCS / "changelog.md" or skip_dir in path.parents:
            continue
        pages.append(path)
    return pages


def pin_install_docs(version: str) -> list[Path]:
    """Point every wheel filename at ``version``; the ``@main`` install line
    is left as it is. Returns the pages that changed."""
    changed = []
    for path in install_pages():
        text = path.read_text(encoding="utf-8")
        new = WHEEL.sub(rf"\g<1>{version}\g<2>", text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(path)
    return changed


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", version.split("-")[0])[:3])


def sections(text: str) -> dict[str, str]:
    """Every released version's section body, newest first; not Unreleased."""
    return {
        m.group(1): m.group(2).strip() for m in SECTION.finditer(text) if m.group(1) != "Unreleased"
    }


def split_section(body: str) -> tuple[str, str]:
    """``(summary, detail)``: the text before the first ``###`` heading, and
    the headings with their lists."""
    m = re.search(r"^### ", body, re.M)
    if not m:
        return body.strip(), ""
    return body[: m.start()].strip(), body[m.start() :].strip()


def summary_problems(summary: str) -> list[str]:
    """What is wrong with a version's teacher summary, in words."""
    if not summary:
        return ["no summary paragraph before the first ### heading"]
    problems = []
    if re.search(r"^\s*([-*+]|\d+\.)\s", summary, re.M):
        return ["the summary is a list; write two or three sentences"]
    sentences = len(SENTENCE_END.findall(unwrap(summary)))
    if not 2 <= sentences <= 3:
        problems.append(f"the summary has {sentences} sentences; write two or three")
    if ISSUE_REF.search(summary):
        problems.append("the summary cites an issue number")
    if PROCESS_WORDS.search(summary):
        problems.append("the summary describes how the work was organised")
    return problems


def changelog_problems(text: str) -> list[str]:
    """Every rule CHANGELOG.md breaks, one line each. Empty when it is fine."""
    problems = []
    for version, body in sections(text).items():
        summary, detail = split_section(body)
        problems += [f"[{version}] {p}" for p in summary_problems(summary)]
        if not detail:
            problems.append(f"[{version}] no ### Added / Changed / Fixed list after the summary")
        for heading in re.findall(r"^### (.+)$", detail, re.M):
            if heading.strip() not in {"Added", "Changed", "Fixed", "Removed", "Security"}:
                problems.append(f"[{version}] heading '### {heading}' is not Added/Changed/Fixed")
        if version_key(version) <= version_key(LAST_PRIVATE):
            refs = sorted(set(ISSUE_REF.findall(body)), key=lambda r: int(r[1:]))
            if refs:
                problems.append(
                    f"[{version}] cites {', '.join(refs)} from the private repository; "
                    "those numbers open unrelated issues here"
                )
            if word := PROCESS_WORDS.search(body):
                problems.append(
                    f"[{version}] mentions '{word.group(0)}' (how the work was organised)"
                )
    return problems


def unwrap(markdown: str) -> str:
    """Join hard-wrapped lines: a GitHub Release renders every newline in its
    body as a line break. Headings, list items, blank lines and fenced code
    keep their own lines; a list item's indented continuation lines and a
    paragraph's lines become one line."""
    out: list[str] = []
    fenced = False
    joinable = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            fenced = not fenced
            out.append(line)
            joinable = False
            continue
        # A heading, an HTML tag, a table row or a quote starts its own line
        # only at the margin: indented, ``<file>`` is a wrapped item's text.
        block_line = line.startswith(("#", "<", "|", ">"))
        starts_block = (
            fenced
            or not stripped
            or block_line
            or re.match(r"([-*+]|\d+\.)\s", stripped) is not None
        )
        if joinable and not starts_block:
            out[-1] = f"{out[-1].rstrip()} {stripped}"
            continue
        out.append(line.rstrip())
        joinable = bool(stripped) and not fenced and not line.startswith(("#", "<", "|"))
    return "\n".join(out).strip()


def notes(version: str) -> str:
    """The GitHub Release body for ``version``: the teacher summary, the update
    command, then the detail folded under *For contributors*."""
    body = sections(CHANGELOG.read_text()).get(version)
    if body is None:
        raise SystemExit(f"no changelog section for {version}")
    summary, detail = split_section(body)
    if not summary:
        raise SystemExit(f"[{version}] has no summary for teachers before its first ### heading")
    parts = [unwrap(summary), UPDATE_LINE]
    if detail:
        parts.append(_fold("For contributors: the full list", unwrap(detail), "<details>"))
    return "\n\n".join(parts) + "\n"


def _fold(summary: str, detail: str, tag: str = '<details markdown="1">') -> str:
    """``detail`` folded under ``summary`` and its count of changes. The site
    needs ``markdown="1"`` (``md_in_html``); GitHub does not."""
    count = len(re.findall(r"^[-*+] ", detail, re.M))
    return (
        f"{tag}\n<summary>{summary} ({count} change{'s' if count != 1 else ''})</summary>\n\n"
        f"{detail}\n\n</details>"
    )


def _labels(detail: str) -> str:
    """Group headings as bold labels, so the site's contents list stays one
    line per version; a blank line keeps the list below a list."""
    detail = re.sub(r"^### (.+)\n(?!\n)", r"**\1**\n\n", detail, flags=re.M)
    detail = re.sub(r"^### (.+)$", r"**\1**", detail, flags=re.M)
    detail = re.sub(r"^#### (.+)\n(?!\n)", r"*\1*\n\n", detail, flags=re.M)
    return re.sub(r"^#### (.+)$", r"*\1*", detail, flags=re.M)


def site_page(text: str) -> str:
    """The documentation site's Changelog page: CHANGELOG.md with each
    version's teacher summary as its lead and the detail folded under *For
    contributors* (``md_in_html``), as on the GitHub Release."""
    parts: list[str] = []
    pos = 0
    for m in SECTION.finditer(text):
        parts.append(text[pos : m.start()])
        pos = m.end()
        heading = m.group(0).split("\n", 1)[0]
        summary, detail = split_section(m.group(2).strip())
        block = [heading]
        if m.group(1) == "Unreleased":
            # Lines land here with every change; the summary comes at release.
            if summary or detail:
                block.append(_fold("Not released yet", f"{summary}\n\n{_labels(detail)}".strip()))
        else:
            if summary:
                block.append(f'<div class="release-summary" markdown="1">\n\n{summary}\n\n</div>')
            if detail:
                block.append(_fold("For contributors: the full list", _labels(detail)))
        parts.append("\n\n".join(block) + "\n\n")
    parts.append(text[pos:])
    return "".join(parts).rstrip() + "\n"


def tag() -> str:
    version = current_version()
    # The pages bump re-pinned go into the release commit with the version.
    pinned = [
        str(path.relative_to(ROOT))
        for path in install_pages()
        if WHEEL.search(path.read_text(encoding="utf-8"))
    ]
    subprocess.run(
        ["git", "add", "pyproject.toml", "CHANGELOG.md", "uv.lock", *pinned], check=True, cwd=ROOT
    )
    subprocess.run(["git", "commit", "-q", "-m", f"Release {version}"], check=True, cwd=ROOT)
    subprocess.run(
        ["git", "tag", "-a", f"v{version}", "-m", f"Release {version}"], check=True, cwd=ROOT
    )
    return f"v{version}"


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        raise SystemExit(__doc__)
    cmd = argv[1]
    if cmd == "version":
        print(current_version())
    elif cmd == "bump":
        version = bump(argv[2] if len(argv) > 2 else "patch")
        release_changelog(version)
        pin_install_docs(version)
        print(version)
    elif cmd == "notes":
        print(notes(argv[2]), end="")
    elif cmd == "site":
        print(site_page(CHANGELOG.read_text()), end="")
    elif cmd == "check":
        problems = changelog_problems(CHANGELOG.read_text())
        for problem in problems:
            print(problem)
        raise SystemExit(1 if problems else 0)
    elif cmd == "tag":
        print(tag())
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
