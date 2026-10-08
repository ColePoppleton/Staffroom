"""Run pupil-facing Python in a subprocess with a hard timeout.

Used by ``trace``, ``bugs`` and ``fade``. This is a convenience fence, not a
security boundary: these are the teacher's own files. What it does provide:

* ``python -I -u`` (isolated: no site, no env-driven imports) in a fresh
  temp working directory with a minimal environment;
* a hard wall-clock timeout, after which the process is killed, plus a CPU
  rlimit as a second guard where the platform supports it;
* captured stdout and stderr, optional stdin;
* a refusal to run files whose AST imports networking modules.
"""

from __future__ import annotations

import ast
import contextlib
import os
import resource
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

BLOCKED_MODULES: frozenset[str] = frozenset(
    {
        "socket",
        "ssl",
        "http",
        "urllib",
        "urllib3",
        "requests",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "telnetlib",
        "xmlrpc",
        "websocket",
        "websockets",
        "asyncio",
        "aiohttp",
        "httpx",
        "subprocess",
        "multiprocessing",
    }
)

DEFAULT_TIMEOUT = 5.0


@dataclass
class RunOutcome:
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    timed_out: bool = False
    seconds: float = 0.0
    blocked_imports: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.blocked_imports

    @property
    def crashed(self) -> bool:
        return self.returncode not in (0, None) and not self.timed_out

    @property
    def exception_name(self) -> str:
        """``ValueError`` from a traceback's last line, else ``""``."""
        for line in reversed(self.stderr.strip().splitlines()):
            head = line.split(":")[0].strip()
            if head.endswith(("Error", "Exception", "Interrupt", "Exit")) and " " not in head:
                return head
        return ""

    def describe(self) -> str:
        if self.blocked_imports:
            return "refused: imports " + ", ".join(self.blocked_imports)
        if self.timed_out:
            return f"timed out after {self.seconds:.1f}s (infinite loop?)"
        if self.crashed:
            return f"crashed: {self.exception_name or f'exit code {self.returncode}'}"
        return "ran"


def blocked_imports(source: str) -> list[str]:
    """Top-level names of blocked modules imported anywhere in ``source``.
    A SyntaxError means we cannot tell, so nothing is reported here; the run
    itself will surface the syntax error."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    found: list[str] = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        for name in names:
            root = name.split(".")[0]
            if root in BLOCKED_MODULES and root not in found:
                found.append(root)
    return found


def _limit_cpu(seconds: float) -> None:  # pragma: no cover - runs in the child
    cpu = int(seconds) + 1
    with contextlib.suppress(ValueError, OSError):
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))


def run_source(
    source: str,
    *,
    stdin: str = "",
    timeout: float = DEFAULT_TIMEOUT,
    filename: str = "program.py",
    extra_files: dict[str, str] | None = None,
    argv: list[str] | None = None,
) -> RunOutcome:
    """Write ``source`` to a temp dir and run it. ``extra_files`` are written
    beside it (e.g. a tracer that imports the program)."""
    blocked = blocked_imports(source)
    if blocked:
        return RunOutcome(blocked_imports=blocked)
    with tempfile.TemporaryDirectory(prefix="staffroom-run-") as tmp:
        work = Path(tmp)
        target = work / filename
        target.write_text(source, encoding="utf-8")
        for name, text in (extra_files or {}).items():
            (work / name).write_text(text, encoding="utf-8")
        return run_file(target, stdin=stdin, timeout=timeout, cwd=work, argv=argv)


def run_file(
    path: Path,
    *,
    stdin: str = "",
    timeout: float = DEFAULT_TIMEOUT,
    cwd: Path | None = None,
    argv: list[str] | None = None,
) -> RunOutcome:
    source = path.read_text(encoding="utf-8", errors="replace")
    blocked = blocked_imports(source)
    if blocked:
        return RunOutcome(blocked_imports=blocked)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(cwd or path.parent),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    cmd = [sys.executable, "-I", "-u", "-X", "utf8", str(path), *(argv or [])]
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd or path.parent),
            env=env,
            preexec_fn=lambda: _limit_cpu(timeout),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return RunOutcome(
            stdout=_text(exc.stdout),
            stderr=_text(exc.stderr),
            timed_out=True,
            seconds=time.perf_counter() - started,
        )
    return RunOutcome(
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
        seconds=time.perf_counter() - started,
    )


def _text(data: object) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return str(data)
