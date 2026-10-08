"""Walk the resources root and describe every file as a :class:`Resource`."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path, PurePosixPath

from staffroom.core.library.model import (
    Resource,
    is_cloud_placeholder_name,
    is_hidden,
    kind_for,
    real_name_from_placeholder,
)


def scan(root: Path) -> Iterator[Resource]:
    """Yield a Resource for each regular file under ``root``. Never raises for
    a single unreadable entry; iCloud placeholders become cloud-only entries
    under their real name."""
    root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _e: None):
        dirnames.sort()
        for filename in sorted(filenames):
            full = Path(dirpath) / filename
            try:
                st = full.stat()
            except OSError:
                continue
            rel = PurePosixPath(full.relative_to(root).as_posix())
            cloud = False
            if is_cloud_placeholder_name(filename):
                real = real_name_from_placeholder(filename)
                rel = rel.with_name(real)
                filename = real
                cloud = True
            yield Resource(
                rel_path=str(rel),
                name=filename,
                ext=rel.suffix.lower(),
                kind=kind_for(rel),
                size=st.st_size,
                mtime=st.st_mtime,
                cloud_only=cloud,
                hidden=is_hidden(rel),
            )
