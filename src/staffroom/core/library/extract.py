"""Text extraction for search and preview. Only the searchable kinds are ever
opened; Office and other binaries are not parsed here or anywhere else."""

from __future__ import annotations

import errno
import logging
from pathlib import Path

from staffroom.core.library.model import Resource
from staffroom.core.log import get_logger

log = get_logger(__name__)
# pypdf is chatty about fonts and dangling references; none of it is actionable here.
logging.getLogger("pypdf").setLevel(logging.ERROR)

TEXT_CAP = 200_000  # characters kept per file
PDF_PAGE_CAP = 20
CLOUD_ERRNOS = frozenset({errno.EDEADLK, getattr(errno, "EDEADLOCK", errno.EDEADLK)})


class CloudOnlyError(OSError):
    """The file is an iCloud placeholder whose bytes are not on disk."""


def _reraise_cloud(exc: OSError, path: Path) -> None:
    if exc.errno in CLOUD_ERRNOS or "deadlock" in str(exc).lower():
        raise CloudOnlyError(exc.errno, f"cloud-only: {path.name}", str(path)) from exc
    raise exc


def read_text(path: Path, cap: int = TEXT_CAP) -> str:
    """UTF-8 (lossy) text of a file, capped. Raises CloudOnlyError for
    evicted iCloud files; other OSErrors propagate."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            return fh.read(cap)
    except OSError as exc:
        _reraise_cloud(exc, path)
        raise  # pragma: no cover - _reraise_cloud always raises


def read_pdf_text(path: Path, page_cap: int = PDF_PAGE_CAP, cap: int = TEXT_CAP) -> str:
    """Text layer of the first ``page_cap`` pages; empty string if none."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(path))
        chunks: list[str] = []
        total = 0
        for i, page in enumerate(reader.pages):
            if i >= page_cap or total >= cap:
                break
            text = page.extract_text() or ""
            chunks.append(text)
            total += len(text)
        return "\n".join(chunks)[:cap].strip()
    except OSError as exc:
        _reraise_cloud(exc, path)
        raise  # pragma: no cover
    except Exception as exc:  # malformed PDF: index by name only
        log.warning("could not read PDF %s: %s", path.name, exc)
        return ""


def extract_text(resource: Resource, root: Path) -> str | None:
    """Text for the index, or None when the kind is not searchable or the
    text layer is empty. Raises CloudOnlyError for evicted files."""
    if not resource.searchable:
        return None
    path = resource.absolute(root)
    text = read_pdf_text(path) if resource.kind == "pdf" else read_text(path)
    return text if text.strip() else None
