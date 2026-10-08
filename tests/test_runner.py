"""Acceptance: the runner kills an infinite loop within the timeout and
reports it; network imports are refused before anything runs."""

import time
from importlib import import_module
from pathlib import Path

from staffroom.core.runner import (
    MAX_OUTPUT_BYTES,
    blocked_imports,
    capped_note,
    limits_note,
    run_source,
    truncation_marker,
)

DOCS = Path(__file__).resolve().parents[1] / "docs"


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
