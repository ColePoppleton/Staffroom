"""Review sheets are today's sheets (#75).

``legacy_sheets.json`` was written by the worksheet tool before sheets were split into
lessons: for every old topic, difficulty, seed, count (and board, level and law family
where they apply) it holds a hash of the whole Document (title, header, every block),
plus the full text of a few for a readable diff. A Review lesson must rebuild each one
exactly, so a seed printed on an old sheet still makes that sheet and its key.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import pytest

from staffroom.core.export import to_text
from staffroom.tools.worksheet import logic
from staffroom.tools.worksheet.sheet import build_document

PINS = json.loads((Path(__file__).with_name("legacy_sheets.json")).read_text(encoding="utf-8"))
DAY = date(2026, 9, 1)


def _document(key: str) -> object:
    topic, difficulty, seed, count, board, level, laws = key.split("|")
    options = logic.Options(
        topic=topic,  # type: ignore[arg-type]
        count=int(count),
        seed=int(seed),
        difficulty=difficulty,  # type: ignore[arg-type]
        level=level,  # type: ignore[arg-type]
        laws=laws,  # type: ignore[arg-type]
    )
    questions = logic.generate(
        topic,
        int(seed),
        int(count),
        difficulty,  # type: ignore[arg-type]
        board=board,
        level=level,  # type: ignore[arg-type]
        laws=laws,  # type: ignore[arg-type]
    )
    return build_document(questions, options, DAY, board=board)


@pytest.mark.parametrize("key", sorted(PINS["texts"]))
def test_review_text_matches_the_pinned_sheet(key: str) -> None:
    doc = _document(key)
    assert to_text(doc.sheet()) + "\n" + to_text(doc.key()) == PINS["texts"][key]  # type: ignore[attr-defined]


def test_every_pinned_document_is_rebuilt_exactly() -> None:
    wrong = [
        key
        for key, digest in PINS["hashes"].items()
        if hashlib.sha256(repr(_document(key)).encode()).hexdigest() != digest
    ]
    assert not wrong, f"{len(wrong)} of {len(PINS['hashes'])} differ, e.g. {wrong[:3]}"
