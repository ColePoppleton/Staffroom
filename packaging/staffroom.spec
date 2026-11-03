# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the self-contained Mac app (#60).

Build with:  just bundle
  (or: uv run python packaging/bundle.py python build/python
       uv run pyinstaller packaging/staffroom.spec --noconfirm --clean)
Output:      dist/Staffroom.app
Check with:  uv run python packaging/smoke.py dist/Staffroom.app

Tools are discovered with pkgutil at runtime, so every submodule of
staffroom is collected explicitly. packaging/bundle.py lists the data files
the package reads by path (tests/test_bundle.py keeps that list complete),
the libraries whose data no hook collects, and fetches the standalone Python
that runs pupil code, which goes into Contents/Resources/pupil-python
(STAFFROOM_BUNDLE_PYTHON overrides where it is read from)."""

import os
import sys
import tomllib
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"
sys.path.insert(0, SPECPATH)
import bundle  # noqa: E402  (packaging/bundle.py)

VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
PYTHON = Path(os.environ.get("STAFFROOM_BUNDLE_PYTHON") or bundle.DEFAULT_PYTHON_DIR)
if not (PYTHON / bundle.PYTHON_BIN).exists():
    raise SystemExit(
        f"No Python for pupil code at {PYTHON}. Run: uv run python packaging/bundle.py python"
    )

hidden = collect_submodules("staffroom", filter=lambda name: ".tests" not in name)
datas = bundle.package_datas(SRC)
for package, files in bundle.EXTERNAL_DATA.items():
    datas += collect_data_files(package, include_py_files=True, includes=list(files))
datas += [
    (str(path), str(Path(bundle.APP_DIR, path.parent.relative_to(PYTHON))))
    for path in sorted(PYTHON.rglob("*"))
    if (path.is_file() or path.is_symlink()) and bundle.ships(path.relative_to(PYTHON))
]

a = Analysis(
    [str(SRC / "staffroom" / "shell" / "app.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden + ["matplotlib.backends.backend_agg", "docx", "reportlab", "pypdf", "openpyxl"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "pytest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtMultimedia",
        "PySide6.QtQuick",
        "PySide6.QtQml",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="staffroom",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(SRC / "staffroom" / "shell" / "assets" / "icon.icns"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="staffroom")
app = BUNDLE(
    coll,
    name="Staffroom.app",
    icon=str(SRC / "staffroom" / "shell" / "assets" / "icon.icns"),
    bundle_identifier="uk.staffroom.launcher",
    info_plist={
        "CFBundleDisplayName": "Staffroom",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "NSHighResolutionCapable": True,
        # The Qt 6.12 wheels (PySide6-Essentials / -Pdf, #4) are built for macOS 14+.
        "LSMinimumSystemVersion": "14.0",
    },
)
