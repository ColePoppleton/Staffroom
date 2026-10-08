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
    registrations = [c for c in calls if c[0] == str(lsregister)]
    assert registrations == [
        [str(lsregister), "-u", str(app)],
        [str(lsregister), "-f", str(target)],
    ]
    assert ["mdimport", str(target)] in calls
    assert any(c[:4] == ["codesign", "--force", "--deep", "--sign"] for c in calls)
