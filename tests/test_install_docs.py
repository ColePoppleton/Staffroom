"""The install instructions in the README and the docs must work today (#80).

Staffroom is not on PyPI, so an install-by-name line (``uv tool install
staffroom``) fails for a colleague, or installs someone else's package if the
name is ever registered. The flag ``extra.published_on_pypi`` in mkdocs.yml
says whether that form is allowed; until it is true, every install line must
point at the GitHub repository.

Since #11 the git line installs from ``@main`` (the released branch), so
``uv tool upgrade staffroom`` moves a copy to the newest release; a line
pinned to a tag would make that command a no-op, so none is allowed. The
line is the same one the Updates card shows (``core.install.INSTALL_LINE``).
``scripts/release.py bump`` still rewrites the wheel filename (#100), so on
every commit it equals the version in pyproject.toml exactly.
"""

import re
import tomllib
from pathlib import Path

from staffroom.core.install import INSTALL_LINE

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# Pages a colleague reads to install. Audits are dated records and quote the
# old line on purpose; docs/changelog.md is a build-time copy of CHANGELOG.md.
SKIP = {DOCS / "changelog.md"}
SKIP_DIRS = {DOCS / "audits"}

# An installer followed (after any options) by the bare package name, e.g.
# "uv tool install staffroom", "pip install -U staffroom", "uvx staffroom".
BY_NAME = re.compile(
    r"\b(?:uv\s+tool\s+install|uv\s+pip\s+install|pipx\s+install|pip3?\s+install|uv\s+add"
    r"|uvx(?:\s+--from)?)(?:\s+--?[\w-]+(?:[=\s]+(?!staffroom\b)[\w.=<>~-]+)?)*"
    r"\s+[\"']?staffroom\b(?![\w./@-])"
)
TAG_PIN = re.compile(r"git\+https://github\.com/ColePoppleton/Staffroom@v\d")
WHEEL = re.compile(r"\bstaffroom-(\d+\.\d+\.\d+)-py3-none-any\.whl")


def _pages() -> list[Path]:
    pages = [ROOT / "README.md"]
    for path in sorted(DOCS.rglob("*.md")):
        if path in SKIP or any(d in path.parents for d in SKIP_DIRS):
            continue
        pages.append(path)
    return pages


def _published_on_pypi() -> bool:
    text = (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    match = re.search(r"^\s+published_on_pypi:\s*(true|false)\s*$", text, re.MULTILINE)
    assert match, "mkdocs.yml must set extra.published_on_pypi: true or false"
    return match.group(1) == "true"


def test_pattern_catches_install_by_name() -> None:
    for line in [
        "uv tool install staffroom",
        "uv tool install --python 3.12 staffroom",
        "pip install -U staffroom",
        "pipx install staffroom",
        "uvx --from staffroom staffroom",
        "uv tool install 'staffroom'",
    ]:
        assert BY_NAME.search(line), line
    for line in [
        "uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@main",
        "uv tool install ./staffroom-0.6.0-py3-none-any.whl",
        "uv tool uninstall staffroom",
        "uv tool upgrade staffroom",
    ]:
        assert not BY_NAME.search(line), line


def test_docs_do_not_install_by_name_until_on_pypi() -> None:
    if _published_on_pypi():
        return
    offenders = [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
        for path in _pages()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if BY_NAME.search(line)
    ]
    assert not offenders, (
        "Staffroom is not on PyPI (mkdocs.yml extra.published_on_pypi: false), so these "
        "lines would fail for a colleague. Install from git+https://github.com/"
        "ColePoppleton/Staffroom@main instead:\n" + "\n".join(offenders)
    )


def test_home_page_readme_and_install_lead_with_the_main_install_line() -> None:
    assert INSTALL_LINE == (
        "uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@main"
    )
    for name in ["README.md", "docs/index.md", "docs/guide/install.md"]:
        lines = [line.strip() for line in (ROOT / name).read_text(encoding="utf-8").splitlines()]
        assert INSTALL_LINE in lines, f"{name} has no line reading: {INSTALL_LINE}"


def test_no_install_line_pins_a_release_tag() -> None:
    """A tag pin makes ``uv tool upgrade staffroom`` say *Nothing to upgrade*."""
    pinned = [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
        for path in _pages()
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if TAG_PIN.search(line)
    ]
    assert not pinned, f"install from @main, not a tag (#11): {pinned}"


def test_updating_page_gives_the_one_command() -> None:
    text = (DOCS / "guide" / "updating.md").read_text(encoding="utf-8")
    assert "uv tool upgrade staffroom" in text


def test_wheel_pins_agree_and_are_released() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    pins = {
        (pin, path.relative_to(ROOT).as_posix())
        for path in _pages()
        for pin in WHEEL.findall(path.read_text(encoding="utf-8"))
    }
    assert pins, "no wheel filename found in the install pages"
    stale = sorted((pin, name) for pin, name in pins if pin != version)
    assert not stale, (
        f"wheel filenames must be staffroom-{version}-py3-none-any.whl, the version in "
        f"pyproject.toml (scripts/release.py bump rewrites them): {stale}"
    )
