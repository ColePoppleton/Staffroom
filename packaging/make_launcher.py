"""Build the thin launcher app: a tiny .app whose executable runs the code
straight from this checkout with uv. Updating the code updates the app;
there is nothing to rebuild or reinstall.

    uv run python packaging/make_launcher.py            # -> dist/Teaching Tools.app
    uv run python packaging/make_launcher.py --install  # also copy into /Applications
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "teaching_tools" / "shell" / "assets"
APP_NAME = "Teaching Tools"

LAUNCHER = """#!/bin/bash
# Thin launcher: runs Teaching Tools from the git checkout with uv, so a
# 'git pull' (or the app's own Update button) is all an update takes.
REPO="{repo}"
UV="{uv}"
export PATH="$(dirname "$UV"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$REPO" || {{
    osascript -e 'display alert "Teaching Tools" message "Repository not found at {repo}"'
    exit 1
}}
exec "$UV" run --quiet tt-gui "$@"
"""


def build(out_dir: Path, repo: Path, uv: Path) -> Path:
    app = out_dir / f"{APP_NAME}.app"
    if app.exists():
        shutil.rmtree(app)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    launcher = macos / "tt-gui"
    launcher.write_text(LAUNCHER.format(repo=repo, uv=uv), encoding="utf-8")
    launcher.chmod(0o755)
    shutil.copy2(ASSETS / "icon.icns", resources / "icon.icns")
    plist = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": "uk.teachingtools.launcher",
        "CFBundleVersion": "1",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "tt-gui",
        "CFBundleIconFile": "icon.icns",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    }
    with (app / "Contents" / "Info.plist").open("wb") as fh:
        plistlib.dump(plist, fh)
    return app


def install(app: Path) -> Path:
    for target_dir in (Path("/Applications"), Path.home() / "Applications"):
        target = target_dir / app.name
        try:
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(app, target, symlinks=True)
        except PermissionError:
            continue
        subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(target)], check=False)
        return target
    msg = "could not write to /Applications or ~/Applications"
    raise SystemExit(msg)


def main() -> None:
    uv = Path(shutil.which("uv") or Path.home() / ".local" / "bin" / "uv").resolve()
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    app = build(out, ROOT, uv)
    print("built", app)
    if "--install" in sys.argv:
        target = install(app)
        print("installed", target)
        if os.environ.get("TT_OPEN"):
            subprocess.run(["open", str(target)], check=False)


if __name__ == "__main__":
    main()
