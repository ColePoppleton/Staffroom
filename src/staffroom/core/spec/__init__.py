"""Specification taxonomies (OCR J277, AQA 8525, Pearson Edexcel 1CP2) as data files.

Used to tag questions, worksheets and library resources. The files are
indicative: check codes and titles against the current published
specification before relying on them in reports. A file may name the
document it was built from in a ``[source]`` table (:func:`source`).

``BOARDS`` is the one list of boards: Settings, the command line's
``--board`` checks and the docs' wording follow it, so a board added here
is offered everywhere."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

BOARDS: dict[str, str] = {
    "ocr": "OCR J277",
    "aqa": "AQA 8525",
    "edexcel": "Pearson Edexcel 1CP2",
}
#: How a sentence names a board's spec points: "OCR and Edexcel spec points".
SHORT_NAMES: dict[str, str] = {"ocr": "OCR", "aqa": "AQA", "edexcel": "Edexcel"}


@dataclass(frozen=True)
class SpecPoint:
    board: str  # a key of BOARDS
    code: str  # "1.2.4"
    title: str
    unit: str  # "1.2 Memory and storage"

    @property
    def tag(self) -> str:
        return f"{self.board}:{self.code}"

    def matches(self, prefix: str) -> bool:
        """``"1.2"`` matches ``1.2``, ``1.2.1``, ``1.2.4`` ..."""
        return self.code == prefix or self.code.startswith(prefix + ".")


def board_choices(sep: str = ", ", last: str = " or ") -> str:
    """``"ocr, aqa or edexcel"``: the board keys for help text and messages."""
    keys = list(BOARDS)
    return sep.join(keys[:-1]) + last + keys[-1] if len(keys) > 1 else keys[0]


@cache
def _load(board: str) -> dict[str, Any]:
    board = board.lower()
    if board not in BOARDS:
        msg = f"unknown board {board!r}; choose from {', '.join(BOARDS)}"
        raise ValueError(msg)
    path = Path(__file__).with_name(f"{board}.toml")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def source(board: str) -> dict[str, str]:
    """The ``[source]`` table: the specification document, issue, date and
    URL the taxonomy was built from; empty when the file does not say."""
    return {str(k): str(v) for k, v in _load(board).get("source", {}).items()}


@cache
def load_taxonomy(board: str) -> tuple[SpecPoint, ...]:
    board = board.lower()
    data = _load(board)
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
