"""Smoke-test a built Mac app before it is published (#60).

    uv run python packaging/smoke.py dist/Staffroom.app

Drives the app's own launcher binary offscreen (``--screenshot`` mode), from
a throwaway home, config and sessions folder, so nothing on the machine is
read or written:

1. the bundled Python for pupil code exists and runs;
2. every tool in ``src/staffroom/tools`` opens (a tool that discovery
   skipped makes the launcher exit 2);
3. runs that cover the risky parts complete: Trace, Bugs and Fade on
   ``examples/year9.py`` (pupil code through ``core/runner`` and the bundled
   Python), Parsons and Worksheet (Word and PDF exports), Marks (charts),
   Pseudocode and Quiz.

Exits non-zero on the first failure, printing the launcher's output and the
end of its log, so the Release workflow stops before it publishes. Prints
the app's size on disk at the end.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bundle  # packaging/bundle.py

ROOT = bundle.ROOT
EXAMPLES = ROOT / "examples"
TOOLS = ROOT / "src" / "staffroom" / "tools"
TIMEOUT = 180  # seconds per launch; a cold start on a CI runner is slow
YEAR9 = "examples/year9.py"

# (tool, extra launcher arguments): each must end with "run ok: <tool>".
RUNS: list[tuple[str, list[str]]] = [
    ("trace", ["--open", YEAR9]),
    ("bugs", ["--open", YEAR9]),
    ("fade", ["--open", YEAR9]),
    ("parsons", ["--open", YEAR9]),  # a Word and a PDF sheet (formats: both)
    ("worksheet", []),  # a Word and a PDF sheet
    ("marks", ["--open", "examples/marks_10x.csv"]),
    ("pseudocode", ["--open", YEAR9]),
    (
        "quiz",
        ["--open", "examples/question_bank.md", "--option", "topics=binary,cpu,loops"],
    ),
]


class SmokeError(Exception):
    pass


def tools_in_source() -> list[str]:
    return sorted(p.name for p in TOOLS.iterdir() if p.is_dir() and (p / "__init__.py").is_file())


def throwaway_env(home: Path) -> dict[str, str]:
    """Only what the app needs, pointing every folder it may write into
    ``home``: the real config, sessions folder and home folder are never seen."""
    (home / "user").mkdir(parents=True)
    (home / "sessions").mkdir()
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home / "user"),
        "TMPDIR": str(home / "tmp"),
        "STAFFROOM_HOME": str(home / "config"),
        "STAFFROOM_SESSIONS": str(home / "sessions"),
        "QT_QPA_PLATFORM": "offscreen",
        "LANG": "en_GB.UTF-8",
    }


def launch(app: Path, args: list[str], env: dict[str, str], cwd: Path) -> str:
    binary = app / "Contents" / "MacOS" / "staffroom"
    try:
        proc = subprocess.run(
            [str(binary), *args],
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise SmokeError(f"{' '.join(args)}: no answer within {TIMEOUT} s") from exc
    out = proc.stdout + proc.stderr
    # 0 saved, 1 refused to save (it would show a path on this machine; the
    # window rendered). 2: no such tool. Anything else is a crash.
    if proc.returncode not in (0, 1) or not ("saved " in out or "REFUSED" in out):
        raise SmokeError(f"{' '.join(args)}: exit {proc.returncode}\n{out}")
    return out


def check_python(app: Path) -> None:
    python = app / "Contents" / "Resources" / bundle.APP_DIR / bundle.PYTHON_BIN
    if not python.exists():
        raise SmokeError(f"no Python for pupil code at {python}")
    proc = subprocess.run(
        [str(python), "-I", "-c", "import sys; print(sys.version.split()[0])"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        raise SmokeError(f"the bundled Python does not start: {proc.stderr}")
    print(f"ok   bundled Python {proc.stdout.strip()}")


def smoke(app: Path, work: Path) -> None:
    env = throwaway_env(work)
    Path(env["TMPDIR"]).mkdir()
    shots = work / "shots"
    # Inputs inside the sessions folder, which the screenshot shows as
    # ~/TeachingSessions; a copy, so no run writes beside the real examples.
    cwd = Path(env["STAFFROOM_SESSIONS"])
    shutil.copytree(EXAMPLES, cwd / "examples")
    check_python(app)
    for tool in tools_in_source():
        launch(app, ["--tool", tool, "--screenshot", str(shots / f"{tool}.png")], env, cwd)
        print(f"ok   {tool} opens")
    for tool, extra in RUNS:
        args = ["--tool", tool, *extra, "--run", "--screenshot", str(shots / f"{tool}-run.png")]
        out = launch(app, args, env, cwd)
        line = next((ln for ln in out.splitlines() if ln.startswith("run ")), "")
        if not line.startswith(f"run ok: {tool}"):
            log = Path(env["STAFFROOM_HOME"]) / "logs" / "staffroom.log"
            tail = log.read_text(errors="replace")[-4000:] if log.exists() else "(no log)"
            raise SmokeError(f"{tool} did not run: {line or out}\n--- log ---\n{tail}")
        print(f"ok   {tool} runs")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("app", type=Path, help="the built Staffroom.app")
    args = parser.parse_args(argv)
    app = args.app.resolve()
    if not (app / "Contents" / "MacOS" / "staffroom").exists():
        print(f"not a built Staffroom.app: {app}", file=sys.stderr)
        return 2
    work = Path(tempfile.mkdtemp(prefix="staffroom-smoke-"))
    try:
        smoke(app, work)
    except SmokeError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)
    size = bundle.tree_size(app)
    python = bundle.tree_size(app / "Contents" / "Resources" / bundle.APP_DIR)
    print(f"size {size / 1e6:.0f} MB on disk ({python / 1e6:.0f} MB of it the pupil-code Python)")
    return 0


if __name__ == "__main__":
    os.umask(0o022)
    sys.exit(main())
