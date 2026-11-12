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

from staffroom.core import spec
from staffroom.core.export import Document, to_text
from staffroom.tools.worksheet.lessons import LEGACY, Settings
from staffroom.tools.worksheet.sheet import make_document

PINS = json.loads((Path(__file__).with_name("legacy_sheets.json")).read_text(encoding="utf-8"))
DAY = date(2026, 9, 1)


def _document(key: str) -> Document:
    """The pinned case made as the tool makes it now: the old topic's Review lesson."""
    topic, difficulty, seed, count, board, level, laws = key.split("|")
    settings = Settings(board=board, level=level, laws=laws)  # type: ignore[arg-type]
    made = make_document(
        LEGACY[topic],
        int(seed),
        int(count),
        difficulty,  # type: ignore[arg-type]
        settings,
        spec.BOARDS,
        DAY,
    )
    return made.doc


def test_every_old_topic_has_a_review_lesson() -> None:
    topics = {key.split("|")[0] for key in PINS["hashes"]}
    assert topics == set(LEGACY)
    assert all(LEGACY[t].review and LEGACY[t].legacy == t for t in topics)


@pytest.mark.parametrize("key", sorted(PINS["texts"]))
def test_review_text_matches_the_pinned_sheet(key: str) -> None:
    doc = _document(key)
    assert to_text(doc.sheet()) + "\n" + to_text(doc.key()) == PINS["texts"][key]


def test_every_pinned_document_is_rebuilt_exactly() -> None:
    wrong = [
        key
        for key, digest in PINS["hashes"].items()
        if hashlib.sha256(repr(_document(key)).encode()).hexdigest() != digest
    ]
    assert not wrong, f"{len(wrong)} of {len(PINS['hashes'])} differ, e.g. {wrong[:3]}"
