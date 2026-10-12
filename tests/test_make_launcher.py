"""packaging/make_launcher.py: the thin .app must run natively (never under
Rosetta, which breaks every arm64 wheel in .venv) and carry the icon."""

import importlib.util
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "packaging" / "make_launcher.py"
spec = importlib.util.spec_from_file_location("make_launcher", SCRIPT)
assert spec and spec.loader
make_launcher = importlib.util.module_from_spec(spec)
sys.modules["make_launcher"] = make_launcher
spec.loader.exec_module(make_launcher)


def test_bundle_runs_natively(tmp_path: Path) -> None:
    app = make_launcher.build(tmp_path, Path("/repo"), Path("/usr/local/bin/uv"))
    assert app == tmp_path / "Staffroom.app"

    with (app / "Contents" / "Info.plist").open("rb") as fh:
        plist = plistlib.load(fh)
    assert plist["LSRequiresNativeExecution"] is True
    assert plist["LSArchitecturePriority"] == ["arm64"]
    assert plist["CFBundleExecutable"] == "staffroom"
    assert plist["CFBundleIdentifier"] == "uk.staffroom.launcher"
    assert plist["CFBundleName"] == "Staffroom"

    script = (app / "Contents" / "MacOS" / "staffroom").read_text()
    assert "arch -arm64" in script
    assert "staffroom" in script.splitlines()[-1]
    assert (app / "Contents" / "Resources" / "icon.icns").exists()


@pytest.mark.skipif(shutil.which("codesign") is None, reason="codesign is macOS only")
def test_bundle_is_ad_hoc_signed(tmp_path: Path) -> None:
    # Spotlight on macOS 26 does not list an unsigned bundle.
    app = make_launcher.build(tmp_path, Path("/repo"), Path("/usr/local/bin/uv"))
    result = subprocess.run(
        ["codesign", "--verify", "--deep", str(app)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_install_forgets_the_dist_copy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        make_launcher.subprocess, "run", lambda argv, **kw: calls.append([str(a) for a in argv])
    )
    lsregister = tmp_path / "lsregister"
    lsregister.write_text("")
    monkeypatch.setattr(make_launcher, "LSREGISTER", str(lsregister))
    app = make_launcher.build(tmp_path / "dist", Path("/repo"), Path("/usr/local/bin/uv"))
    applications = tmp_path / "Applications"
    applications.mkdir()

    target = make_launcher.install(app, (applications,))

    assert target == applications / "Staffroom.app"
    assert (target / "Contents" / "MacOS" / "staffroom").exists()
    # The build is gone, so Spotlight cannot list a second Staffroom from dist/.
    assert not app.exists()
    registrations = [c for c in calls if c[0] == str(lsregister)]
    assert registrations == [
        [str(lsregister), "-u", str(app)],
        [str(lsregister), "-f", str(target)],
    ]
    assert ["mdimport", str(target)] in calls
    assert any(c[:4] == ["codesign", "--force", "--deep", "--sign"] for c in calls)


def test_bundle_version_follows_the_package(tmp_path: Path) -> None:
    # Finder's Get Info showed 0.1.0 whatever the checkout ran (#69).
    from staffroom import __version__

    app = make_launcher.build(tmp_path, Path("/repo"), Path("/usr/local/bin/uv"))
    with (app / "Contents" / "Info.plist").open("rb") as fh:
        plist = plistlib.load(fh)
    assert plist["CFBundleShortVersionString"] == make_launcher.package_version()
    assert plist["CFBundleShortVersionString"] == __version__
    assert plist["CFBundleVersion"] == __version__

    app = make_launcher.build(tmp_path, Path("/repo"), Path("/uv"), version="0.7.0rc1")
    with (app / "Contents" / "Info.plist").open("rb") as fh:
        plist = plistlib.load(fh)
    assert plist["CFBundleShortVersionString"] == "0.7.0rc1"
    assert plist["CFBundleVersion"] == "0.7.0"


def _version(app: Path) -> str:
    with (app / "Contents" / "Info.plist").open("rb") as fh:
        return str(plistlib.load(fh)["CFBundleShortVersionString"])


def test_reinstall_updates_the_bundle_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Deleting and recopying the bundle made Spotlight drop Staffroom until it
    # re-indexed (#79): the installed folder must stay the same folder.
    calls: list[list[str]] = []
    monkeypatch.setattr(
        make_launcher.subprocess, "run", lambda argv, **kw: calls.append([str(a) for a in argv])
    )
    lsregister = tmp_path / "lsregister"
    lsregister.write_text("")
    monkeypatch.setattr(make_launcher, "LSREGISTER", str(lsregister))
    applications = tmp_path / "Applications"
    applications.mkdir()
    dist = tmp_path / "dist"

    app = make_launcher.build(dist, Path("/repo"), Path("/uv"), version="0.6.0")
    target = make_launcher.install(app, (applications,))
    inode = target.stat().st_ino
    contents_inode = (target / "Contents").stat().st_ino
    stale = target / "Contents" / "Resources" / "old.icns"
    stale.write_bytes(b"left over from an older build")
    stale_dir = target / "Contents" / "Frameworks"
    stale_dir.mkdir()
    (stale_dir / "gone.txt").write_text("x")
    calls.clear()

    app = make_launcher.build(dist, Path("/new-repo"), Path("/uv"), version="0.7.0")
    again = make_launcher.install(app, (applications,))

    assert again == target
    assert target.stat().st_ino == inode
    assert (target / "Contents").stat().st_ino == contents_inode
    assert _version(target) == "0.7.0"
    assert "/new-repo" in (target / "Contents" / "MacOS" / "staffroom").read_text()
    assert (target / "Contents" / "Resources" / "icon.icns").exists()
    assert not stale.exists()
    assert not stale_dir.exists()
    assert ["codesign", "--force", "--deep", "--sign", "-", str(target)] in calls
    registrations = [c for c in calls if c[0] == str(lsregister)]
    assert registrations == [
        [str(lsregister), "-u", str(app)],
        [str(lsregister), "-f", str(target)],
    ]
    assert ["mdimport", str(target)] in calls


@pytest.mark.skipif(shutil.which("codesign") is None, reason="codesign is macOS only")
def test_bundle_updated_in_place_is_validly_signed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Real codesign, but never tell Launch Services or Spotlight about a temp folder.
    monkeypatch.setattr(make_launcher, "register", lambda app: None)
    monkeypatch.setattr(make_launcher, "unregister", lambda app: None)
    applications = tmp_path / "Applications"
    applications.mkdir()
    dist = tmp_path / "dist"
    make_launcher.install(
        make_launcher.build(dist, Path("/repo"), Path("/uv"), version="0.6.0"), (applications,)
    )
    target = make_launcher.install(
        make_launcher.build(dist, Path("/repo2"), Path("/uv"), version="0.7.0"), (applications,)
    )

    assert _version(target) == "0.7.0"
    result = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", str(target)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
