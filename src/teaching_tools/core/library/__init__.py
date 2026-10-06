"""The Resource Library: index, search, preview-text extraction and tags for
the teacher's resources folder. GUI-free; the shell renders it, the CLI
drives it, and plugins reach it through :class:`ResourceService`.

Rules (docs/PHASES.md): the resources root is read-only; tags and notes live
in a sidecar JSON; Office and other binary files are never parsed, only
opened externally; cloud-only placeholders are marked, never fatal.
"""

from teaching_tools.core.library.model import Kind, Resource, SearchHit
from teaching_tools.core.library.service import LibraryService, ResourceService

__all__ = ["Kind", "LibraryService", "Resource", "ResourceService", "SearchHit"]
