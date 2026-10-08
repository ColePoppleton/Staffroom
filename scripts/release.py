"""Release helper: Keep a Changelog + semantic versioning + git tags.

    uv run python scripts/release.py version              # print the current version
    uv run python scripts/release.py bump patch|minor|major
    uv run python scripts/release.py notes 0.2.0          # that version's changelog section
    uv run python scripts/release.py tag                  # commit the bump and tag it

``just release <part>`` runs bump, lock, tag and push. The tag triggers
.github/workflows/release.yml, which builds the wheel and sdist and creates
the GitHub Release with the notes.
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
UNRELEASED = "## [Unreleased]"


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
    today = dt.date.today().isoformat()
    new = (
        f"{head}{UNRELEASED}\n\n## [{version}] - {today}\n{body.strip()}\n\n{tail}".rstrip() + "\n"
    )
    CHANGELOG.write_text(new)
    return body.strip()


def notes(version: str) -> str:
    text = CHANGELOG.read_text()
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m:
        raise SystemExit(f"no changelog section for {version}")
    return m.group(1).strip()


def tag() -> str:
    version = current_version()
    subprocess.run(
        ["git", "add", "pyproject.toml", "CHANGELOG.md", "uv.lock"], check=True, cwd=ROOT
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
        print(version)
    elif cmd == "notes":
        print(notes(argv[2]))
    elif cmd == "tag":
        print(tag())
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
