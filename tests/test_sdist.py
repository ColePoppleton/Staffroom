"""The source distribution (#22) carries the package, its tests and the
examples they read, and nothing else: no docs site or audit screenshots, no
``.claude/``, no CI or packaging scripts. It was 40 MB; now it is about 1 MB.

Building needs uv and hatchling (the network, or uv's cache), so the test runs
only with ``STAFFROOM_WHEEL_TEST=1``, as the install-line workflow's wheel job
sets it."""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 2_000_000
# Hatch adds PKG-INFO, pyproject.toml, the readme, the licence and .gitignore itself.
TOP_LEVEL = {
    "PKG-INFO",
    "pyproject.toml",
    "README.md",
    "LICENSE",
    ".gitignore",
    "CHANGELOG.md",
    "conftest.py",
    "src",
    "tests",
    "examples",
}

pytestmark = [
    pytest.mark.checkout,
    pytest.mark.skipif(
        os.environ.get("STAFFROOM_WHEEL_TEST") != "1" or shutil.which("uv") is None,
        reason="builds the sdist and wheels with uv (needs the network); "
        "set STAFFROOM_WHEEL_TEST=1, as the install-line workflow does",
    ),
]


def build(kind: str, source: Path, out: Path) -> Path:
    uv = shutil.which("uv")
    assert uv is not None
    subprocess.run(
        [uv, "build", f"--{kind}", "-o", str(out), str(source)],
        check=True,
        capture_output=True,
        timeout=300,
    )
    return next(out.glob("staffroom-*.tar.gz" if kind == "sdist" else "staffroom-*.whl"))


def contents(wheel: Path) -> dict[str, int]:
    """Every file in the wheel by its CRC: equal maps, equal wheels."""
    with zipfile.ZipFile(wheel) as zf:
        return {info.filename: info.CRC for info in zf.infolist()}


def test_sdist_is_small_and_builds_the_wheel_the_checkout_builds(tmp_path: Path) -> None:
    sdist = build("sdist", REPO_ROOT, tmp_path / "sdist")
    assert sdist.stat().st_size < MAX_BYTES, f"{sdist.name}: {sdist.stat().st_size:,} bytes"

    with tarfile.open(sdist) as tar:
        names = {name.split("/", 1)[1] for name in tar.getnames() if "/" in name}
    assert {name.split("/", 1)[0] for name in names} == TOP_LEVEL
    tracked = subprocess.run(
        ["git", "ls-files", "src", "tests", "examples"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    missing = set(tracked) - names
    assert not missing, f"tracked files left out of the sdist: {sorted(missing)}"

    from_sdist = build("wheel", sdist, tmp_path / "from-sdist")
    from_checkout = build("wheel", REPO_ROOT, tmp_path / "from-checkout")
    assert contents(from_sdist) == contents(from_checkout)
