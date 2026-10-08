"""Document model: what a worksheet or report *is*, independent of format."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date


@dataclass(frozen=True)
class Heading:
    text: str
    level: int = 2


@dataclass(frozen=True)
class Paragraph:
    text: str
    style: str = "normal"  # normal | muted | instruction


@dataclass(frozen=True)
class Code:
    text: str
    caption: str = ""


@dataclass(frozen=True)
class Numbered:
    """Numbered items. ``answer_lines`` leaves ruled space under each item;
    ``code`` sets the items in monospace."""

    items: tuple[str, ...]
    start: int = 1
    answer_lines: int = 0
    code: bool = False


@dataclass(frozen=True)
class TableBlock:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    monospace: bool = False


@dataclass(frozen=True)
class HintBox:
    text: str
    title: str = "Hint"


@dataclass(frozen=True)
class PageBreak:
    pass


Block = Heading | Paragraph | Code | Numbered | TableBlock | HintBox | PageBreak


@dataclass
class Section:
    blocks: list[Block] = field(default_factory=list)
    answers: bool = False
    title: str = ""

    def add(self, block: Block) -> Section:
        self.blocks.append(block)
        return self


@dataclass(frozen=True)
class HouseStyle:
    """Text the teacher wants on every sheet: a header prefix (school or
    department) and a footer line beside the page number."""

    header: str = ""
    footer: str = ""


@dataclass
class Document:
    title: str
    topic: str = ""
    date: date | None = None
    subtitle: str = ""
    sections: list[Section] = field(default_factory=list)
    style: HouseStyle = field(default_factory=HouseStyle)

    def section(self, title: str = "", *, answers: bool = False) -> Section:
        section = Section(title=title, answers=answers)
        self.sections.append(section)
        return section

    @property
    def date_text(self) -> str:
        return self.date.strftime("%d %B %Y") if self.date else ""

    @property
    def header_text(self) -> str:
        parts = [self.style.header, self.title, self.topic, self.date_text]
        return "   ·   ".join(p for p in parts if p)

    @property
    def footer_text(self) -> str:
        return self.style.footer

    def sheet(self) -> Document:
        """The pupil-facing document: everything but the answer sections."""
        return replace(self, sections=[s for s in self.sections if not s.answers])

    def key(self) -> Document:
        """The answer key: only the answer sections, retitled."""
        return replace(
            self,
            title=f"{self.title} — Answer key",
            sections=[s for s in self.sections if s.answers],
        )

    @property
    def has_answers(self) -> bool:
        return any(s.answers for s in self.sections)
