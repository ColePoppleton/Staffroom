"""No text assumes the boards are only OCR and AQA (#62).

Any paragraph of the app's code or the docs that names two or more exam
boards must name every board in ``core.spec.BOARDS``, so adding a board to
that list shows up here wherever a sentence or a mapping lists the others.
The board names come from ``spec.SHORT_NAMES``, not from this file."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from staffroom.core import spec

ROOT = Path(__file__).resolve().parents[1]
#: OCR ERL and AQA pseudocode are languages, not boards: Pearson Edexcel 1CP2
#: has no pseudocode of its own (it assesses Python), so the pseudocode tool
#: and its page list two languages on purpose.
LANGUAGE_FILES = ("src/staffroom/tools/pseudocode/", "docs/tools/pseudocode.md")
#: Dated records of what was true then.
HISTORY = ("docs/audits/", "CHANGELOG.md", "docs/PHASES.md", "docs/ROADMAP.md")


def _files() -> list[Path]:
    found = [*ROOT.glob("src/staffroom/**/*.py"), *ROOT.glob("docs/**/*.md")]
    found += [ROOT / "README.md", ROOT / "CLAUDE.md", ROOT / "examples" / "README.md"]
    keep = []
    for path in found:
        rel = path.relative_to(ROOT).as_posix()
        if path.exists() and not rel.startswith(LANGUAGE_FILES + HISTORY) and "/tests/" not in rel:
            keep.append(path)
    return keep


def _boards_in(chunk: str) -> set[str]:
    named = set()
    for key, short in spec.SHORT_NAMES.items():
        if re.search(rf"\b{re.escape(short)}\b", chunk) or f'"{key}"' in chunk:
            named.add(key)
    return named


@pytest.mark.checkout  # reads the docs, README and CLAUDE.md beside the package
def test_a_list_of_boards_names_them_all() -> None:
    every = set(spec.BOARDS)
    assert set(spec.SHORT_NAMES) == every
    problems = []
    for path in _files():
        for chunk in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
            named = _boards_in(chunk)
            if len(named) >= 2 and named != every:
                first = chunk.strip().splitlines()[0][:80]
                missing = ", ".join(sorted(every - named))
                problems.append(f"{path.relative_to(ROOT)}: {first!r} (missing {missing})")
    assert not problems, "\n".join(problems)
