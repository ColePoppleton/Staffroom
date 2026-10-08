"""Specification taxonomies (OCR J277, AQA 8525) as data files.

Used to tag questions, worksheets and library resources. The files are
indicative: check codes and titles against the current published
specification before relying on them in reports."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path

BOARDS: dict[str, str] = {"ocr": "OCR J277", "aqa": "AQA 8525"}


@dataclass(frozen=True)
class SpecPoint:
    board: str  # ocr | aqa
    code: str  # "1.2.4"
    title: str
    unit: str  # "1.2 Memory and storage"

    @property
    def tag(self) -> str:
        return f"{self.board}:{self.code}"

    def matches(self, prefix: str) -> bool:
        """``"1.2"`` matches ``1.2``, ``1.2.1``, ``1.2.4`` ..."""
        return self.code == prefix or self.code.startswith(prefix + ".")


@cache
def load_taxonomy(board: str) -> tuple[SpecPoint, ...]:
    board = board.lower()
    if board not in BOARDS:
        msg = f"unknown board {board!r}; choose from {', '.join(BOARDS)}"
        raise ValueError(msg)
    path = Path(__file__).with_name(f"{board}.toml")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    points: list[SpecPoint] = []
    for unit in data.get("units", []):
        unit_label = f"{unit['code']} {unit['title']}"
        for point in unit.get("points", []):
            points.append(SpecPoint(board, str(point["code"]), str(point["title"]), unit_label))
    return tuple(points)


def find(tag: str) -> SpecPoint | None:
    """``"ocr:1.2.4"`` -> the point, or None."""
    board, _, code = tag.partition(":")
    for point in load_taxonomy(board) if board.lower() in BOARDS else ():
        if point.code == code:
            return point
    return None


def describe(tag: str) -> str:
    point = find(tag)
    return f"{tag} {point.title}" if point else tag
