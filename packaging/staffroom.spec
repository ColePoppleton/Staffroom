# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Staffroom launcher.

Build with:  just app   (or: uv run pyinstaller packaging/staffroom.spec --noconfirm)
Output:      dist/Staffroom.app

Tools are discovered with pkgutil at runtime, so every submodule of
staffroom is collected explicitly, along with the data files it reads
(shell assets, spec TOML files, the tracer script, examples)."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"

hidden = collect_submodules("staffroom")
datas = collect_data_files("staffroom", includes=["**/*.svg", "**/*.png", "**/*.icns", "**/*.toml", "**/tracer_script.py", "**/fonts/*.ttf", "**/fonts/*-OFL.txt"])
datas += [(str(ROOT / "examples"), "examples")]

a = Analysis(
    [str(SRC / "staffroom" / "shell" / "app.py")],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden + ["matplotlib.backends.backend_agg", "docx", "reportlab", "pypdf", "openpyxl"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtQuick", "PySide6.QtQml"],
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
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
        # The Qt 6.12 wheels (PySide6-Essentials / -Pdf, #4) are built for macOS 14+.
        "LSMinimumSystemVersion": "14.0",
    },
)
