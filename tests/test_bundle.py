"""The self-contained Mac app (#60), checked without building it.

The first test build ran but skipped Trace (``tracer_script.py`` was not in
the bundle) and failed Word exports (python-docx's templates were missing),
and pupil code would have been started with the app itself as the Python.
These tests keep the spec's lists complete from the source tree, check the
pin for the pupil-code Python, and unpack a fake Python archive. Nothing
here builds a bundle or downloads anything.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import io
import re
import tarfile
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

from staffroom.core import install

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PACKAGE = SRC / "staffroom"
SPEC = ROOT / "packaging" / "staffroom.spec"
WORKFLOWS = ROOT / ".github" / "workflows"
FILE_NAME = re.compile(r"[\w.-]+\.py")


def _load_bundle() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bundle", ROOT / "packaging" / "bundle.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bundle = _load_bundle()


def _shipped_modules() -> list[Path]:
    return [p for p in PACKAGE.rglob("*.py") if "tests" not in p.relative_to(PACKAGE).parts]


def _collected() -> set[str]:
    """Package-relative paths the spec collects as data."""
    return {
        (Path(dest) / Path(source).name).as_posix() for source, dest in bundle.package_datas(SRC)
    }


# -- data files the package reads ----------------------------------------------


def test_every_non_python_file_in_the_package_is_collected() -> None:
    expected = {
        p.relative_to(SRC).as_posix()
        for p in PACKAGE.rglob("*")
        if p.is_file()
        and p.suffix not in (".py", ".pyc")
        and not {"tests", "__pycache__"} & set(p.relative_to(PACKAGE).parts)
        and p.name != ".DS_Store"
    }
    assert expected, "the package has data files (icons, fonts, spec TOML)"
    assert expected <= _collected(), sorted(expected - _collected())
    assert not any("/tests/" in path for path in _collected())


def test_every_python_file_read_as_text_is_collected() -> None:
    """A module that builds a path to a ``.py`` file sitting beside it
    (``Path(__file__).with_name("tracer_script.py")``) reads it as data:
    PyInstaller only ships compiled modules, so the file must be collected
    too. Found by scanning the source, so a new one cannot be forgotten."""
    read_as_text: set[str] = set()
    for module in _shipped_modules():
        for node in ast.walk(ast.parse(module.read_text(encoding="utf-8"))):
            for name in _path_names(node):
                beside = module.with_name(name)
                if FILE_NAME.fullmatch(name) and beside.is_file():
                    read_as_text.add(beside.relative_to(SRC).as_posix())
    assert "staffroom/tools/trace/tracer_script.py" in read_as_text
    assert read_as_text <= _collected(), sorted(read_as_text - _collected())
    assert set(bundle.DATA_PY) <= read_as_text, "DATA_PY lists only files something reads"


def _path_names(node: ast.AST) -> list[str]:
    """File names a path is built from: ``x.with_name("a.py")`` and ``x / "a.py"``."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "with_name"
    ):
        args: list[ast.expr] = list(node.args)
    elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        args = [node.right]
    else:
        return []
    return [a.value for a in args if isinstance(a, ast.Constant) and isinstance(a.value, str)]


def test_python_docx_templates_are_collected() -> None:
    """python-docx has no PyInstaller hook and reads its templates as
    ``docx/parts/../templates/default-header.xml``, which only resolves when
    the ``parts`` folder exists on disk: the first test build failed Word
    exports for want of both."""
    import docx

    package = Path(docx.__file__).parent
    globs = bundle.EXTERNAL_DATA["docx"]
    collected = {p for g in globs for p in package.glob(g) if p.is_file()}
    assert {p for p in (package / "templates").rglob("*") if p.is_file()} <= collected
    assert any(p.parent.name == "parts" for p in collected)
    hdrftr = (package / "parts" / "hdrftr.py").read_text()
    assert '"..", "templates", "default-header.xml"' in hdrftr  # still read that way


def test_the_spec_uses_the_lists_and_the_project_version() -> None:
    text = SPEC.read_text(encoding="utf-8")
    assert "bundle.package_datas(SRC)" in text
    assert "bundle.EXTERNAL_DATA" in text
    assert "bundle.APP_DIR" in text  # Contents/Resources/pupil-python, see core/runner
    assert '"CFBundleShortVersionString": VERSION' in text
    assert not re.search(r'"CFBundleShortVersionString":\s*"', text), "read from pyproject"


# -- the Python for pupil code ---------------------------------------------------


def test_the_pupil_python_is_pinned_and_checked() -> None:
    pin = bundle.python_pin()
    assert re.fullmatch(r"[0-9a-f]{64}", pin["sha256"])
    assert re.fullmatch(r"\d{8}", pin["release"]), "a dated release, never latest"
    assert pin["url"].startswith(
        "https://github.com/astral-sh/python-build-standalone/releases/download/"
        f"{pin['release']}/cpython-{pin['version']}%2B{pin['release']}-"
    )
    assert pin["url"].endswith("-aarch64-apple-darwin-install_only_stripped.tar.gz")
    assert "latest" not in pin["url"]
    # The same minor version the app is built and tested with.
    minor = (ROOT / ".python-version").read_text().strip()
    assert pin["version"].startswith(minor + ".")


def test_the_runner_looks_where_the_spec_puts_the_python() -> None:
    from staffroom.core import runner

    assert Path(bundle.APP_DIR) / bundle.PYTHON_BIN == runner.BUNDLED_PYTHON
    # PyInstaller puts the app's own Python library at "Python": a name that
    # differs only in case would collide on a Mac.
    assert bundle.APP_DIR.lower() != "python"


def _fake_python_archive(path: Path) -> str:
    """A tiny archive shaped like python-build-standalone's install_only."""
    members = {
        "python/bin/python3.13": b"#!/bin/sh\n",
        "python/lib/python3.13/os.py": b"",
        "python/lib/python3.13/test/test_os.py": b"",
        "python/lib/python3.13/tkinter/__init__.py": b"",
        "python/lib/libpython3.13.dylib": b"",
        "python/include/python3.13/Python.h": b"",
        "python/share/man/man1/python3.1": b"",
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o755
            archive.addfile(info, io.BytesIO(data))
        link = tarfile.TarInfo("python/bin/python3")
        link.type = tarfile.SYMTYPE
        link.linkname = "python3.13"
        archive.addfile(link)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fetch_checks_the_hash_then_unpacks_and_trims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "cpython.tar.gz"
    digest = _fake_python_archive(archive)
    pin = tmp_path / "python.toml"
    pin.write_text(
        '[python]\nversion = "3.13.0"\nrelease = "20990101"\n'
        'url = "https://github.com/astral-sh/python-build-standalone/releases/download/x"\n'
        f'sha256 = "{digest}"\n'
    )
    monkeypatch.setattr(bundle, "download", lambda *a: pytest.fail("downloaded"))
    dest = bundle.fetch_python(tmp_path / "python", archive, pin)
    assert (dest / "bin" / "python3").is_symlink()
    assert (dest / "lib" / "python3.13" / "os.py").exists()
    for gone in ("include", "share", "lib/python3.13/test", "lib/python3.13/tkinter"):
        assert not (dest / gone).exists(), gone
    assert not (dest / "lib" / "libpython3.13.dylib").exists()

    assert bundle.ships(Path("lib/python3.13/os.py"))
    assert not bundle.ships(Path(bundle.PIN_MARKER))
    assert not bundle.ships(Path("lib/python3.13/__pycache__/os.cpython-313.pyc"))
    assert "bundle.ships(" in SPEC.read_text()
    # Unpacked once from the pinned archive: the next build reuses it.
    assert bundle.fetch_python(dest, pin=pin) == dest

    pin.write_text(pin.read_text().replace(digest, "0" * 64))
    with pytest.raises(SystemExit, match="SHA-256"):
        bundle.fetch_python(tmp_path / "other", archive, pin)
    assert not (tmp_path / "other").exists()


def test_download_refuses_anything_but_python_build_standalone(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="refusing"):
        bundle.download("https://example.invalid/python.tar.gz", tmp_path / "x")
    assert not (tmp_path / "x").exists()


# -- the release ------------------------------------------------------------------


def test_the_release_asset_is_the_name_the_app_tells_teachers() -> None:
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert bundle.project_version() == version
    assert bundle.asset_name(version) == install.APP_ASSET_PATTERN.replace("<version>", version)


def test_the_release_publishes_only_a_smoke_tested_app() -> None:
    """The Bundle workflow builds, smoke-tests and zips the app; the Release
    workflow runs it first and only then creates the GitHub Release, so a
    failing smoke test publishes nothing."""
    built = (WORKFLOWS / "bundle.yml").read_text()
    steps = [
        "packaging/bundle.py python",
        "pyinstaller packaging/staffroom.spec",
        "packaging/smoke.py",
        "ditto",
    ]
    positions = [built.index(step) for step in steps]
    assert positions == sorted(positions), "build, then smoke test, then zip"
    release = (WORKFLOWS / "release.yml").read_text()
    assert "uses: ./.github/workflows/bundle.yml" in release
    assert re.search(r"needs:\s*\[?[^\n]*\bbundle\b", release)
    assert release.index("needs:") < release.index("gh release create")
