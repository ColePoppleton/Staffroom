"""Build the thin launcher app: a tiny .app whose executable runs the code
straight from this checkout with uv. Updating the code updates the app;
there is nothing to rebuild or reinstall.

    uv run python packaging/make_launcher.py            # -> dist/Staffroom.app
    uv run python packaging/make_launcher.py --install  # also install into /Applications
"""

from __future__ import annotations

import os
import plistlib
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "staffroom" / "shell" / "assets"
APP_NAME = "Staffroom"

LAUNCHER = """#!/bin/bash
# Thin launcher: runs Staffroom from the git checkout with uv, so a
# 'git pull' (or the app's own Update button) is all an update takes.
REPO="{repo}"
UV="{uv}"
export PATH="$(dirname "$UV"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd "$REPO" || {{
    osascript -e 'display alert "Staffroom" message "Repository not found at {repo}"'
    exit 1
}}
# Finder may start a script executable under Rosetta; a universal Python then
# comes up as x86_64 and none of the arm64 wheels in .venv can load. Pin the
# architecture when the tool to do so exists.
if [ -x /usr/bin/arch ]; then
    exec /usr/bin/arch -arm64 "$UV" run --quiet staffroom "$@"
fi
exec "$UV" run --quiet staffroom "$@"
"""


def package_version(root: Path = ROOT) -> str:
    """The version in pyproject.toml: what ``staffroom.__version__`` reports
    once the checkout is synced. Read from the file so a fresh build never
    depends on what happens to be installed."""
    with (root / "pyproject.toml").open("rb") as fh:
        return str(tomllib.load(fh)["project"]["version"])


def bundle_version(version: str) -> str:
    """``CFBundleVersion`` wants up to three dot-separated integers; keep the
    numeric release part of a version such as ``0.6.0rc1`` or ``0.6.0+local``."""
    match = re.match(r"\d+(\.\d+){0,2}", version)
    return match.group(0) if match else "0"


LSREGISTER = (
    "/System/Library/Frameworks/CoreServices.framework/Frameworks/"
    "LaunchServices.framework/Support/lsregister"
)


def build(out_dir: Path, repo: Path, uv: Path, version: str | None = None) -> Path:
    """Write the bundle. ``version`` defaults to the package version, so
    Finder's Get Info matches what the app shows in its sidebar."""
    version = version or package_version()
    app = out_dir / f"{APP_NAME}.app"
    if app.exists():
        shutil.rmtree(app)
    macos = app / "Contents" / "MacOS"
    resources = app / "Contents" / "Resources"
    macos.mkdir(parents=True)
    resources.mkdir(parents=True)
    launcher = macos / "staffroom"
    launcher.write_text(LAUNCHER.format(repo=repo, uv=uv), encoding="utf-8")
    launcher.chmod(0o755)
    shutil.copy2(ASSETS / "icon.icns", resources / "icon.icns")
    plist = {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": "uk.staffroom.launcher",
        "CFBundleVersion": bundle_version(version),
        "CFBundleShortVersionString": version,
        "CFBundlePackageType": "APPL",
        "CFBundleExecutable": "staffroom",
        "CFBundleIconFile": "icon.icns",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        # Never run the launcher (and so Python) under Rosetta.
        "LSRequiresNativeExecution": True,
        "LSArchitecturePriority": ["arm64"],
    }
    with (app / "Contents" / "Info.plist").open("wb") as fh:
        plistlib.dump(plist, fh)
    sign(app)
    return app


def sign(app: Path) -> None:
    """Ad-hoc sign the bundle. Spotlight on recent macOS does not list an
    unsigned bundle at all; an ad-hoc signature is enough for a local app."""
    if shutil.which("codesign"):
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=False)


def install(app: Path, target_dirs: tuple[Path, ...] | None = None) -> Path:
    """Copy the bundle into /Applications (or ~/Applications when that is not
    writable) and make it the one copy Launch Services knows about.

    An existing bundle is updated in place rather than deleted and recopied:
    macOS treats a new bundle folder as a new app, and Spotlight drops the
    old entry at once but lists the new one only after it re-indexes, which
    can take hours when indexing is paused (#79)."""
    if target_dirs is None:
        target_dirs = (Path("/Applications"), Path.home() / "Applications")
    for target_dir in target_dirs:
        target = target_dir / app.name
        try:
            if target.is_dir() and not target.is_symlink():
                sync_tree(app, target)
            else:
                if target.exists() or target.is_symlink():
                    target.unlink()
                shutil.copytree(app, target, symlinks=True)
        except PermissionError:
            continue
        subprocess.run(["xattr", "-dr", "com.apple.quarantine", str(target)], check=False)
        sign(target)
        unregister(app)
        register(target)
        return target
    msg = "could not write to /Applications or ~/Applications"
    raise SystemExit(msg)


def sync_tree(src: Path, dst: Path) -> None:
    """Make the existing folder ``dst`` match ``src`` without replacing it:
    overwrite every file from ``src``, create missing folders, and remove
    anything ``src`` no longer has. ``dst`` itself (and every folder both
    share) keeps its inode."""
    wanted = {child.name for child in src.iterdir()}
    for child in dst.iterdir():
        if child.name not in wanted:
            _remove(child)
    for child in src.iterdir():
        out = dst / child.name
        if child.is_symlink():
            if out.exists() or out.is_symlink():
                _remove(out)
            out.symlink_to(os.readlink(child))
        elif child.is_dir():
            if out.is_symlink() or (out.exists() and not out.is_dir()):
                _remove(out)
            if not out.exists():
                out.mkdir()
                shutil.copystat(child, out)
            sync_tree(child, out)
        else:
            if out.is_symlink() or out.is_dir():
                _remove(out)
            shutil.copy2(child, out)


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def unregister(app: Path) -> None:
    """Forget the build in dist/ so Launch Services knows one bundle only:
    the installed copy. Otherwise `open -a` and Spotlight may pick the
    stale one."""
    if Path(LSREGISTER).exists():
        subprocess.run([LSREGISTER, "-u", str(app)], check=False)


def register(app: Path) -> None:
    """Tell Launch Services and Spotlight about the bundle so it shows up in
    Spotlight and opens by name straight away."""
    if Path(LSREGISTER).exists():
        subprocess.run([LSREGISTER, "-f", str(app)], check=False)
    if shutil.which("mdimport"):
        subprocess.run(["mdimport", str(app)], check=False)


def main() -> None:
    uv = Path(shutil.which("uv") or Path.home() / ".local" / "bin" / "uv").resolve()
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    app = build(out, ROOT, uv)
    print("built", app)
    if "--install" in sys.argv:
        target = install(app)
        print("installed", target)
        if os.environ.get("STAFFROOM_OPEN"):
            subprocess.run(["open", str(target)], check=False)


if __name__ == "__main__":
    main()
