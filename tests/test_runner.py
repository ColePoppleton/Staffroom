"""Acceptance: the runner kills an infinite loop within the timeout and
reports it; network imports are refused before anything runs."""

import time

from staffroom.core.runner import blocked_imports, run_source


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
