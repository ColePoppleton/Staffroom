"""What the Library's column is narrowed to (#122): the type filter and the
tag filter (#111) together. Both narrow the tree and the search results, and
the column's footer says what is left: ``3 Python files tagged loops``.

The narrowing is the tree's alone. The library's own count (#30) stays one
tally over everything listable; this module never changes it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from staffroom.core.library.model import Kind

#: How a kind reads in a sentence: ``3 Python files``, ``2 text files``.
KIND_LABELS: dict[str, str] = {
    "archive": "archive",
    "audio": "audio",
    "csv": "CSV",
    "database": "database",
    "diagram": "diagram",
    "image": "image",
    "markdown": "Markdown",
    "office": "Office",
    "other": "other",
    "pdf": "PDF",
    "python": "Python",
    "scratch": "Scratch",
    "text": "text",
    "video": "video",
}

ALL = "all"


@dataclass(frozen=True)
class LibraryFilter:
    """``kind`` is a :data:`~staffroom.core.library.model.Kind` or ``"all"``;
    ``tags`` are the tag filter's choice, every one of them required."""

    kind: str = ALL
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind != ALL and self.kind not in KIND_LABELS:
            raise ValueError(f"not a file type: {self.kind!r}")

    @property
    def kinds(self) -> list[Kind] | None:
        """For ``LibraryService.resources`` and ``search``: None is every kind."""
        return None if self.kind == ALL else [cast(Kind, self.kind)]

    @property
    def active(self) -> bool:
        """True when the tree lists less than the whole library."""
        return self.kind != ALL or bool(self.tags)

    def describe(self, n: int) -> str:
        """``3 Python files tagged loops``, ``1 file tagged loops + gcse``,
        ``0 PDF files``: the line the footer starts with while filtered."""
        noun = "file" if n == 1 else "files"
        if self.kind != ALL:
            noun = f"{KIND_LABELS[self.kind]} {noun}"
        line = f"{n} {noun}"
        if self.tags:
            line += " tagged " + " + ".join(self.tags)
        return line
