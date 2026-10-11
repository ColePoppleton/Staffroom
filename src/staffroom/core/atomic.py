"""Write a small text file so that a failed write cannot truncate it (#125).

The text goes to a temporary file beside the target, which is flushed and then
renamed over the target with :func:`os.replace`. Until the rename the old file
is untouched; after it the new one is complete. A failure on the way removes
the temporary file and re-raises the ``OSError``.

Used for ``config.toml``, ``usage.toml`` and the library's tags sidecar."""

from __future__ import annotations

import contextlib
import errno
import os
import secrets
import stat
from pathlib import Path

_TEMP_ATTEMPTS = 8


def _open_temp(folder: Path, name: str) -> tuple[int, Path]:
    """Create a hidden, unique temporary file in ``folder``. Mode ``0o666``
    goes through the umask, so a new file gets the mode ``open()`` would give
    it (``mkstemp`` would make it ``0o600``)."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    for _ in range(_TEMP_ATTEMPTS):
        tmp = folder / f".{name}.{secrets.token_hex(4)}.tmp"
        try:
            return os.open(tmp, flags, 0o666), tmp
        except FileExistsError:
            continue
    raise FileExistsError(errno.EEXIST, "no free temporary file name", str(folder))


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Replace ``path`` with ``text`` in one step. The folder must exist.

    An existing file keeps its permission bits. One that is not writable (made
    read-only on purpose) is left alone with ``PermissionError``, as opening it
    for writing would have done: a rename would otherwise ignore its mode. A
    symlink is followed, so the link stays and its target is replaced."""
    target = Path(os.path.realpath(path))
    data = text.encode(encoding)
    try:
        mode: int | None = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        mode = None
    else:
        if not os.access(target, os.W_OK):
            raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), str(path))
    fd, tmp = _open_temp(target.parent, target.name)
    try:
        with open(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
