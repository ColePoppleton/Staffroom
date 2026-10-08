# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Teaching Tools launcher.

Build with:  just app   (or: uv run pyinstaller packaging/tt-gui.spec --noconfirm)
Output:      dist/Teaching Tools.app

Tools are discovered with pkgutil at runtime, so every submodule of
teaching_tools is collected explicitly, along with the data files it reads
(shell assets, spec TOML files, the tracer script, examples)."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
SRC = ROOT / "src"

hidden = collect_submodules("teaching_tools")
datas = collect_data_files("teaching_tools", includes=["**/*.svg", "**/*.png", "**/*.icns", "**/*.toml", "**/tracer_script.py"])
datas += [(str(ROOT / "examples"), "examples")]

a = Analysis(
    [str(SRC / "teaching_tools" / "shell" / "app.py")],
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
    name="tt-gui",
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(SRC / "teaching_tools" / "shell" / "assets" / "icon.icns"),
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="tt-gui")
app = BUNDLE(
    coll,
    name="Teaching Tools.app",
    icon=str(SRC / "teaching_tools" / "shell" / "assets" / "icon.icns"),
    bundle_identifier="uk.teachingtools.launcher",
    info_plist={
        "CFBundleDisplayName": "Teaching Tools",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
        "LSMinimumSystemVersion": "12.0",
    },
)
