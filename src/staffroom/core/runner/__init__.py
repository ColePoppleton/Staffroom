"""Run pupil-facing Python in a subprocess with a hard timeout.

Used by ``trace``, ``bugs`` and ``fade``. This is a convenience fence, not a
security boundary: these are the teacher's own files. What it does provide:

* ``python -I -u`` (isolated: no site, no env-driven imports) in a fresh
  temp working directory with a minimal environment;
* a hard wall-clock timeout, after which the process is killed, plus a CPU
  rlimit as a second guard where the platform supports it;
* captured stdout and stderr, each capped at ``MAX_OUTPUT_BYTES`` so a print
  flood cannot eat the Mac's memory (the rest is read and discarded; the
  outcome says so and the text ends with a marker), optional stdin;
* a refusal to run files whose AST imports networking or process modules,
  including ``__import__("…")`` / ``importlib.import_module("…")`` with a
  literal name.

What it does not do: it does not stop ``os.system``, file writes, a computed
import name or a large allocation. ``limits_note`` is the sentence the tools
show a teacher; ``docs/guide/running-code.md`` is the long version.
"""

from __future__ import annotations

import ast
import contextlib
import os
import resource
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

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

# Calls that import by name; only a literal first argument is checked.
IMPORT_CALLS: frozenset[str] = frozenset(
    {"__import__", "importlib.import_module", "importlib.__import__", "import_module"}
)

DEFAULT_TIMEOUT = 5.0
MAX_OUTPUT_BYTES = 1024 * 1024  # per stream
_CHUNK = 64 * 1024
_DOCS_PAGE = "Running pupil code"


def _kb(limit: int) -> str:
    return f"{limit // 1024} KB"


def truncation_marker(limit: int = MAX_OUTPUT_BYTES) -> str:
    """The line appended to a capped stream. ``tools/trace/tracer_script.py``
    writes the same wording for output capped inside the child."""
    return f"[output truncated at {_kb(limit)}]\n"


def capped_note(limit: int = MAX_OUTPUT_BYTES) -> str:
    return f"output capped at {_kb(limit)}"


def limits_note(timeout: float) -> str:
    """One teacher-facing sentence for a panel description: what the run is
    limited to and where the full story is."""
    return (
        f"Runs the program in a separate Python process: {timeout:.0f} s limit, "
        f"output capped at {MAX_OUTPUT_BYTES // (1024 * 1024)} MB, network imports refused. "
        f"Not a security sandbox (your own files only); see {_DOCS_PAGE} in the docs."
    )


@dataclass
class RunOutcome:
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    timed_out: bool = False
    seconds: float = 0.0
    blocked_imports: list[str] = field(default_factory=list)
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    output_limit: int = MAX_OUTPUT_BYTES

    @property
    def truncated(self) -> bool:
        """Either stream hit the cap; its text ends with ``truncation_marker``."""
        return self.stdout_truncated or self.stderr_truncated

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
            text = f"timed out after {self.seconds:.1f}s (infinite loop?)"
        elif self.crashed:
            text = f"crashed: {self.exception_name or f'exit code {self.returncode}'}"
        else:
            text = "ran"
        if self.truncated:
            text += "; " + capped_note(self.output_limit)
        return text


def blocked_imports(source: str) -> list[str]:
    """Top-level names of blocked modules imported anywhere in ``source``:
    ``import``/``from`` statements and ``__import__`` / ``importlib``
    calls with a literal module name. Best effort: a computed name gets
    past this, and the docs say so. A SyntaxError means we cannot tell, so
    nothing is reported here; the run itself will surface the syntax error."""
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
        elif isinstance(node, ast.Call) and _call_name(node.func) in IMPORT_CALLS:
            first = node.args[0] if node.args else None
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                names = [first.value]
        for name in names:
            root = name.split(".")[0]
            if root in BLOCKED_MODULES and root not in found:
                found.append(root)
    return found


def _call_name(func: ast.expr) -> str:
    """``__import__`` or ``importlib.import_module`` for the callee, else ``""``."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        return f"{func.value.id}.{func.attr}"
    return ""


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
    output_limit: int = MAX_OUTPUT_BYTES,
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
        return run_file(
            target, stdin=stdin, timeout=timeout, cwd=work, argv=argv, output_limit=output_limit
        )


def run_file(
    path: Path,
    *,
    stdin: str = "",
    timeout: float = DEFAULT_TIMEOUT,
    cwd: Path | None = None,
    argv: list[str] | None = None,
    output_limit: int = MAX_OUTPUT_BYTES,
) -> RunOutcome:
    source = path.read_text(encoding="utf-8", errors="replace")
    blocked = blocked_imports(source)
    if blocked:
        return RunOutcome(blocked_imports=blocked, output_limit=output_limit)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(cwd or path.parent),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    cmd = [sys.executable, "-I", "-u", "-X", "utf8", str(path), *(argv or [])]
    started = time.perf_counter()
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(cwd or path.parent),
        env=env,
        preexec_fn=lambda: _limit_cpu(timeout),
    )
    # Readers start after the fork, so preexec_fn never runs beside our threads.
    out = _BoundedReader(_pipe(proc.stdout), output_limit)
    err = _BoundedReader(_pipe(proc.stderr), output_limit)
    feeder = threading.Thread(target=_feed, args=(_pipe(proc.stdin), stdin), daemon=True)
    feeder.start()
    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        proc.wait()
    # A grandchild could keep a pipe open; do not hang the app for it.
    out.close(grace=2.0)
    err.close(grace=2.0)
    return RunOutcome(
        stdout=out.text(),
        stderr=err.text(),
        returncode=None if timed_out else proc.returncode,
        timed_out=timed_out,
        seconds=time.perf_counter() - started,
        stdout_truncated=out.truncated,
        stderr_truncated=err.truncated,
        output_limit=output_limit,
    )


def _pipe(stream: IO[bytes] | None) -> IO[bytes]:
    if stream is None:  # pragma: no cover - Popen with PIPE always sets them
        msg = "subprocess pipe missing"
        raise RuntimeError(msg)
    return stream


def _feed(pipe: IO[bytes], text: str) -> None:
    """Write stdin and close it, so ``input()`` past the end raises EOFError
    as it did with ``subprocess.run(input=...)``. Broken pipe = child quit first."""
    try:
        if text:
            pipe.write(text.encode("utf-8"))
    except (OSError, ValueError):
        pass
    finally:
        with contextlib.suppress(OSError, ValueError):
            pipe.close()


class _BoundedReader:
    """Drain a pipe on a thread, keeping the first ``limit`` bytes and
    counting the rest, so the child never blocks on a full pipe and we never
    hold more than the cap."""

    def __init__(self, pipe: IO[bytes], limit: int) -> None:
        self._pipe = pipe
        self._limit = limit
        self._data = bytearray()
        self.dropped = 0
        self._thread = threading.Thread(target=self._drain, daemon=True)
        self._thread.start()

    @property
    def truncated(self) -> bool:
        return self.dropped > 0

    def _drain(self) -> None:
        read = getattr(self._pipe, "read1", self._pipe.read)
        with contextlib.suppress(OSError, ValueError):
            while chunk := read(_CHUNK):
                room = self._limit - len(self._data)
                if room > 0:
                    self._data += chunk[:room]
                self.dropped += max(0, len(chunk) - room)

    def close(self, *, grace: float) -> None:
        self._thread.join(timeout=grace)
        with contextlib.suppress(OSError, ValueError):
            self._pipe.close()

    def text(self) -> str:
        text = bytes(self._data).decode("utf-8", errors="replace")
        if not self.truncated:
            return text
        # The cut may fall inside a multi-byte character; drop that fragment.
        text = text.rstrip("\ufffd")
        if text and not text.endswith("\n"):
            text += "\n"
        return text + truncation_marker(self._limit)
