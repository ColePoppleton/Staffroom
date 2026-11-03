"""Acceptance: the runner kills an infinite loop within the timeout and
reports it; network imports are refused before anything runs."""

import sys
import time
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

from staffroom.core import runner
from staffroom.core.plugin import ToolError
from staffroom.core.runner import (
    BUNDLED_PYTHON,
    MAX_OUTPUT_BYTES,
    NO_INTERPRETER,
    blocked_imports,
    capped_note,
    interpreter,
    limits_note,
    run_source,
    truncation_marker,
)

DOCS = Path(__file__).resolve().parents[1] / "docs"
# Read before any test pretends to be the frozen app (which replaces sys.executable).
REAL_PYTHON = sys.executable


def test_runs_and_captures_output_with_stdin() -> None:
    out = run_source("name = input()\nprint('hi', name)\nprint(2 + 2)\n", stdin="Ada\n")
    assert out.ok and out.stdout == "hi Ada\n4\n" and out.stderr == ""
    assert out.describe() == "ran"


def test_infinite_loop_is_killed_within_timeout() -> None:
    started = time.perf_counter()
    out = run_source("while True:\n    pass\n", timeout=1.0)
    elapsed = time.perf_counter() - started
    assert out.timed_out and not out.ok
    assert elapsed < 4.0
    assert "timed out" in out.describe()


def test_crash_is_reported_with_exception_name() -> None:
    out = run_source("x = int('abc')\n")
    assert out.crashed and out.exception_name == "ValueError"
    assert out.describe() == "crashed: ValueError"
    out = run_source("while True\n    pass\n")
    assert out.crashed and out.exception_name == "SyntaxError"


def test_blocked_imports_refused() -> None:
    assert blocked_imports("import socket\nfrom urllib import request\nimport os\n") == [
        "socket",
        "urllib",
    ]
    assert blocked_imports("import os\n") == []
    out = run_source("import socket\nprint('never')\n")
    assert out.blocked_imports == ["socket"] and out.stdout == "" and not out.ok
    assert out.describe().startswith("refused")


def test_isolated_cwd_and_extra_files() -> None:
    out = run_source(
        "import os\nprint(sorted(os.listdir('.')))\nprint(open('data.txt').read())\n",
        extra_files={"data.txt": "hello"},
    )
    assert out.ok and "['data.txt', 'program.py']" in out.stdout and "hello" in out.stdout


FLOOD = "i = 0\nwhile True:\n    print('line', i, 'x' * 200)\n    i += 1\n"


def test_print_flood_is_capped_and_memory_stays_bounded() -> None:
    out = run_source(FLOOD, timeout=2.0)
    assert out.timed_out and out.stdout_truncated and out.truncated
    # The cap, plus one marker line: never hundreds of megabytes.
    assert MAX_OUTPUT_BYTES <= len(out.stdout.encode()) <= MAX_OUTPUT_BYTES + 100
    assert out.stdout.rstrip("\n").endswith(truncation_marker().strip())
    assert "output capped" in out.describe() and "timed out" in out.describe()


def test_finished_flood_is_capped_with_marker_but_still_ok() -> None:
    out = run_source("print('a' * 2_000_000)\n", timeout=10.0)
    assert out.returncode == 0 and out.ok and out.stdout_truncated and not out.stderr_truncated
    assert out.stdout.endswith(truncation_marker())
    # Kept text, a newline before the marker, the marker: nothing more.
    assert len(out.stdout) <= MAX_OUTPUT_BYTES + 1 + len(truncation_marker())
    assert out.describe() == "ran; " + capped_note()


def test_stderr_is_capped_independently() -> None:
    out = run_source("import sys\nsys.stderr.write('e' * 2_000_000)\nprint('fine')\n")
    assert out.stdout == "fine\n" and not out.stdout_truncated
    assert out.stderr_truncated and out.stderr.endswith(truncation_marker())


def test_output_under_the_cap_is_untouched() -> None:
    out = run_source("print('a' * 1000)\n")
    assert out.ok and not out.truncated and out.stdout == "a" * 1000 + "\n"
    assert out.describe() == "ran"


def test_cap_is_configurable_and_cuts_on_a_character_boundary() -> None:
    out = run_source("print('é' * 100)\n", output_limit=11)
    assert out.stdout_truncated
    kept = out.stdout[: -len(truncation_marker(11))]
    assert kept == "é" * 5 + "\n" and "\ufffd" not in out.stdout


def test_import_calls_with_literal_names_are_caught() -> None:
    assert blocked_imports("__import__('socket')\n") == ["socket"]
    assert blocked_imports("import importlib\nimportlib.import_module('urllib.request')\n") == [
        "urllib"
    ]
    assert blocked_imports("from importlib import import_module\nimport_module('ssl')\n") == ["ssl"]
    assert blocked_imports("importlib.__import__('http')\n") == ["http"]
    # Best effort only: a computed name is not caught, and we do not claim it is.
    assert blocked_imports("name = 'soc' + 'ket'\n__import__(name)\n") == []
    assert blocked_imports("__import__('os')\n") == []


@pytest.mark.checkout
def test_limits_are_stated_where_a_teacher_reads_them() -> None:
    note = limits_note(10.0)
    assert "10 s" in note and "1 MB" in note and "not a security" in note.lower()
    assert "Running pupil code" in note
    page = DOCS / "guide" / "running-code.md"
    text = page.read_text(encoding="utf-8")
    for claim in ("1 MB", "os.system", "__import__", "not a security boundary", "temporary"):
        assert claim in text, claim
    for tool in ("trace", "bugs", "fade"):
        panel = import_module(f"staffroom.tools.{tool}.panel").panel_spec()
        assert "Running pupil code" in panel.description, tool


# -- the Mac app (#60): pupil code needs a Python that is not the app ------


@pytest.fixture
def frozen_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Pretend to be the PyInstaller bundle: ``sys.frozen`` set,
    ``sys._MEIPASS`` its Frameworks folder and ``sys.executable`` the app's
    own binary (which does not exist here, so running it would fail). Returns
    the Frameworks folder; no bundle is built."""
    contents = tmp_path / "Staffroom.app" / "Contents"
    frameworks = contents / "Frameworks"
    frameworks.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(frameworks), raising=False)
    monkeypatch.setattr(sys, "executable", str(contents / "MacOS" / "staffroom"))
    return frameworks


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record the command line of every process the runner starts."""
    calls: list[list[str]] = []
    real = runner.subprocess.Popen

    def recording(cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        calls.append(list(cmd))
        return real(cmd, *args, **kwargs)

    monkeypatch.setattr(runner.subprocess, "Popen", recording)
    return calls


def test_unfrozen_runs_pupil_code_with_this_python(spawned: list[list[str]]) -> None:
    assert interpreter() == Path(sys.executable)
    assert run_source("print(1)\n").ok
    assert spawned[0][0] == sys.executable


def test_frozen_app_runs_pupil_code_with_its_bundled_python(
    frozen_app: Path, spawned: list[list[str]]
) -> None:
    """In the app ``sys.executable`` is the app itself; the program runs in
    the standalone CPython under ``_MEIPASS``, still in a subprocess with
    the temp working directory and the timeout."""
    bundled = frozen_app / BUNDLED_PYTHON
    bundled.parent.mkdir(parents=True)
    bundled.symlink_to(REAL_PYTHON)  # stands in for the standalone CPython
    assert interpreter() == bundled

    out = run_source("import os\nprint(os.path.basename(os.getcwd()))\n")
    assert out.ok, out.stderr
    assert out.stdout.startswith("staffroom-run-")  # a fresh temp folder, not the app's
    # -B as well as -I: isolated mode ignores PYTHONDONTWRITEBYTECODE, and a
    # .pyc written inside the app breaks its code signature.
    assert spawned[-1][:3] == [str(bundled), "-I", "-B"]
    assert sys.executable not in spawned[-1]

    started = time.perf_counter()
    out = run_source("while True:\n    pass\n", timeout=1.0)
    assert out.timed_out and time.perf_counter() - started < 4.0


def test_frozen_app_without_its_python_says_so_and_runs_nothing(
    frozen_app: Path, spawned: list[list[str]]
) -> None:
    """Never fall back to ``sys.executable`` (the app) or to running the
    program in-process: a teacher-facing ToolError, and no process."""
    with pytest.raises(ToolError) as caught:
        run_source("print('never')\n")
    assert str(caught.value) == NO_INTERPRETER
    assert "Download" in caught.value.next_step
    assert spawned == []
