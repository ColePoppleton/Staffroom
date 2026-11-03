"""Helpers for the self-contained Mac app (#60), shared by
``packaging/staffroom.spec``, ``packaging/smoke.py``, the Bundle workflow and
``tests/test_bundle.py``.

    uv run python packaging/bundle.py python build/python        # fetch, check, unpack, trim
    uv run python packaging/bundle.py python build/python --from cpython.tar.gz
    uv run python packaging/bundle.py asset-name                 # Staffroom-<version>-macos.zip
    uv run python packaging/bundle.py size dist/Staffroom.app    # bytes on disk

The app needs three things a plain PyInstaller run misses:

* **data files the package reads by path** (``Path(__file__).with_name(…)``):
  every non-Python file under ``src/staffroom`` plus the few ``.py`` files
  that are read as text, never imported (:data:`DATA_PY`);
* **data files of libraries without a PyInstaller hook**: python-docx reads
  ``docx/templates/*.xml`` beside its modules (:data:`EXTERNAL_DATA`);
* **a Python for pupil code**: inside the app ``sys.executable`` is the app,
  so a standalone CPython (pinned in ``packaging/python.toml``) goes into
  ``Contents/Resources/pupil-python``, and ``core/runner`` starts it there.

Standard library only: the release job runs this before anything is built.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import tarfile
import tempfile
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PIN = ROOT / "packaging" / "python.toml"
DEFAULT_PYTHON_DIR = ROOT / "build" / "python"

# Read as text through Path(__file__), never imported: PyInstaller compiles
# modules into its archive, so these must be collected as data as well.
DATA_PY = ("staffroom/tools/trace/tracer_script.py",)

# Libraries whose data files PyInstaller's hooks do not collect, with the
# files to collect (globs inside the package, for collect_data_files).
EXTERNAL_DATA: dict[str, tuple[str, ...]] = {
    # python-docx reads templates/*.xml as docx/parts/../templates/…: the
    # parts folder must exist on disk too, so one file of it is collected.
    "docx": ("templates/**/*", "parts/__init__.py"),
}

# Not needed to run a pupil's program from Trace or Bugs, and about a third
# of the unpacked size. tkinter goes with Tcl/Tk: a turtle or Tk program has
# no window to open from a run inside Staffroom anyway.
TRIM = (
    "include",
    "share",
    "lib/pkgconfig",
    "lib/itcl*",
    "lib/tcl*",
    "lib/tk*",
    "lib/thread*",
    "lib/libtcl*",
    "lib/libtk*",
    # The interpreter is linked statically; the shared library is for embedding.
    "lib/libpython3*.dylib",
    "lib/python3.*/test",
    "lib/python3.*/idlelib",
    "lib/python3.*/tkinter",
    "lib/python3.*/turtledemo",
    "lib/python3.*/ensurepip",
    "lib/python3.*/site-packages/pip*",
    "lib/python3.*/config-3.*",
    "lib/python3.*/lib-dynload/_tkinter*",
    "lib/python3.*/lib-dynload/_test*",
    "lib/python3.*/lib-dynload/xxlimited*",
    "bin/idle3*",
    "bin/pip*",
    "bin/pydoc3*",
    "bin/python3*-config",
)
PYTHON_BIN = Path("bin") / "python3"
# Its folder inside the app. Not "python": macOS file names ignore case, and
# PyInstaller already puts the app's own "Python" library there.
APP_DIR = "pupil-python"
# Written beside the unpacked Python (not shipped): the SHA-256 it came from.
PIN_MARKER = ".staffroom-pin"


# -- what the package reads ---------------------------------------------------


def package_datas(src: Path = SRC) -> list[tuple[str, str]]:
    """``(file, destination folder)`` pairs, as a spec's ``datas``, for every
    file under ``src/staffroom`` that the package reads at run time and that
    PyInstaller would not otherwise collect: all non-Python files outside
    ``tests/`` and caches, and :data:`DATA_PY`."""
    package = src / "staffroom"
    found: list[tuple[str, str]] = []
    for path in sorted(package.rglob("*")):
        rel = path.relative_to(src)
        if not path.is_file() or _skipped(rel):
            continue
        if path.suffix in (".py", ".pyc") and rel.as_posix() not in DATA_PY:
            continue
        found.append((str(path), rel.parent.as_posix()))
    return found


def _skipped(rel: Path) -> bool:
    return any(part in ("tests", "__pycache__") for part in rel.parts) or rel.name == ".DS_Store"


# -- the Python for pupil code ------------------------------------------------


def python_pin(pin: Path = PIN) -> dict[str, str]:
    with pin.open("rb") as fh:
        data = tomllib.load(fh)["python"]
    return {key: str(data[key]) for key in ("version", "release", "url", "sha256")}


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(tarball: Path, expected: str) -> None:
    actual = sha256_of(tarball)
    if actual != expected.lower():
        msg = f"{tarball.name}: SHA-256 is {actual}, packaging/python.toml pins {expected}"
        raise SystemExit(msg)


def download(url: str, target: Path) -> None:
    if not url.startswith("https://github.com/astral-sh/python-build-standalone/releases/"):
        msg = f"refusing to download a Python from outside python-build-standalone: {url}"
        raise SystemExit(msg)
    with urllib.request.urlopen(url, timeout=120) as response, target.open("wb") as out:
        shutil.copyfileobj(response, out)


def unpack(tarball: Path, dest: Path) -> Path:
    """Unpack a python-build-standalone ``install_only`` archive (one
    top-level ``python/`` folder) into ``dest``, replacing what was there,
    and trim it. Returns ``dest``."""
    with tempfile.TemporaryDirectory(prefix="staffroom-python-") as tmp:
        with tarfile.open(tarball) as archive:
            archive.extractall(tmp, filter="data")
        unpacked = Path(tmp) / "python"
        if not (unpacked / PYTHON_BIN).exists():
            msg = f"{tarball.name} has no python/{PYTHON_BIN}: not an install_only build"
            raise SystemExit(msg)
        trim(unpacked)
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(unpacked), dest)
    return dest


def trim(python: Path) -> list[str]:
    """Remove :data:`TRIM` from an unpacked Python; returns what went."""
    removed: list[str] = []
    for pattern in TRIM:
        for path in sorted(python.glob(pattern)):
            removed.append(path.relative_to(python).as_posix())
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
    return removed


def fetch_python(dest: Path, tarball: Path | None = None, pin: Path = PIN) -> Path:
    """The pinned Python, checked and unpacked into ``dest``. Downloads it
    unless ``tarball`` (an archive already here) is given; either way the
    SHA-256 must match the pin before anything is unpacked. A ``dest``
    already unpacked from the pinned archive is reused (see :data:`PIN_MARKER`)."""
    wanted = python_pin(pin)
    marker = dest / PIN_MARKER
    if tarball is None and marker.is_file() and marker.read_text().strip() == wanted["sha256"]:
        return dest  # already unpacked from this exact archive
    with tempfile.TemporaryDirectory(prefix="staffroom-python-dl-") as tmp:
        archive = tarball
        if archive is None:
            archive = Path(tmp) / "python.tar.gz"
            download(wanted["url"], archive)
        verify(archive, wanted["sha256"])
        unpack(archive, dest)
    marker.write_text(wanted["sha256"] + "\n")
    return dest


# -- the release asset ---------------------------------------------------------


def project_version(root: Path = ROOT) -> str:
    with (root / "pyproject.toml").open("rb") as fh:
        return str(tomllib.load(fh)["project"]["version"])


def asset_name(version: str) -> str:
    """The zipped app attached to each GitHub Release."""
    return f"Staffroom-{version}-macos.zip"


def tree_size(path: Path) -> int:
    """Bytes on disk under ``path``, counting each symlink once as a link."""
    return sum(p.lstat().st_size for p in path.rglob("*") if p.is_file() or p.is_symlink())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bundle.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    py = sub.add_parser("python", help="fetch, check and unpack the pinned Python")
    py.add_argument("dest", type=Path, nargs="?", default=DEFAULT_PYTHON_DIR)
    py.add_argument("--from", dest="tarball", type=Path, help="use this archive, no download")
    sub.add_parser("asset-name", help="print the release asset's file name")
    size = sub.add_parser("size", help="print bytes on disk under a folder")
    size.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "python":
        dest = fetch_python(args.dest, args.tarball)
        print(f"{dest}: Python {python_pin()['version']}, {tree_size(dest) / 1e6:.0f} MB")
    elif args.command == "asset-name":
        print(asset_name(project_version()))
    else:
        print(tree_size(args.path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
