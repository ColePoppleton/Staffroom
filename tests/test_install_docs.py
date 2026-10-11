"""The install instructions in the README and the docs must work today (#80).

Staffroom is not on PyPI, so an install-by-name line (``uv tool install
staffroom``) fails for a colleague, or installs someone else's package if the
name is ever registered. The flag ``extra.published_on_pypi`` in mkdocs.yml
says whether that form is allowed; until it is true, every install line must
point at the GitHub repository, pinned to a released tag.

``scripts/release.py bump`` rewrites the pins and the wheel filename (#100),
so on every commit they equal the version in pyproject.toml exactly.
"""

import re
import tomllib
from pathlib import Path

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
GIT_PIN = re.compile(r"git\+https://github\.com/ColePoppleton/Staffroom@v(\d+\.\d+\.\d+)")
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
        "uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@v0.6.0",
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
        "ColePoppleton/Staffroom@vX.Y.Z instead:\n" + "\n".join(offenders)
    )


def test_home_page_readme_and_install_lead_with_a_pinned_github_install() -> None:
    for name in ["README.md", "docs/index.md", "docs/guide/install.md"]:
        text = (ROOT / name).read_text(encoding="utf-8")
        assert GIT_PIN.search(text), f"{name} has no pinned git+https install line"


def test_install_pins_agree_and_are_released() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version = project["project"]["version"]
    pins = {
        (pin, path.relative_to(ROOT).as_posix())
        for path in _pages()
        for rx in (GIT_PIN, WHEEL)
        for pin in rx.findall(path.read_text(encoding="utf-8"))
    }
    assert pins, "no pinned install line found"
    stale = sorted((f"v{pin}", name) for pin, name in pins if pin != version)
    assert not stale, (
        f"install lines must pin v{version}, the version in pyproject.toml "
        f"(scripts/release.py bump rewrites them): {stale}"
    )
