"""What the result strip says about a run, as plain data (no Qt).

The shell's result strip shows a tick or a cross, a short outcome line, and
one button ("chip") per file written. This module turns a
:class:`~staffroom.core.plugin.RunResult` into those parts, so the rules are
tested without a window and every tool gets them without code of its own.

A chip is the file's kind (``PDF``, ``DOCX``, ``CSV`` …) and a short label.
The label comes from ``RunResult.labels`` when the tool names the file, else
from the file name:

* a sheet and its key (``stem.pdf`` / ``stem_key.pdf``, as
  :func:`staffroom.core.export.export` writes them) are ``Sheet`` and ``Key``;
* files that share a name prefix are told apart by the rest of their names
  (``marks_distribution.csv`` / ``marks_questions.csv`` → ``Distribution``,
  ``Questions``; ``year9_bug1.py`` → ``Bug 1``);
* anything else (one file, or files that differ only in kind) keeps its stem.

Chips are ordered by kind, printable first (PDF, DOCX, spreadsheets, images,
then code and text), keeping the tool's order within a kind.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

KEY_SUFFIX = "_key"
SEPARATOR = " · "

# Lower sorts first. Kinds not listed sort after these, in the tool's order.
KIND_ORDER = {"PDF": 0, "DOCX": 1, "XLSX": 2, "CSV": 3, "PNG": 4, "TXT": 5, "MD": 6, "PY": 7}

_LETTERS_DIGITS = re.compile(r"^([A-Za-z]+)(\d+)$")


@dataclass(frozen=True)
class FileChip:
    path: Path
    kind: str  # "PDF"; "" for a file without an extension
    label: str  # "Sheet"


def file_kind(path: Path) -> str:
    return path.suffix.lstrip(".").upper()


def _humanise(tokens: Sequence[str]) -> str:
    words: list[str] = []
    for token in tokens:
        match = _LETTERS_DIGITS.match(token)
        words.extend(match.groups() if match else [token])
    text = " ".join(w for w in words if w)
    return text[:1].upper() + text[1:]


def _common_prefix(stems: Sequence[list[str]]) -> int:
    """How many leading ``_``-separated tokens every stem shares, leaving at
    least one token of the shortest stem."""
    shortest = min(len(s) for s in stems)
    n = 0
    while n < shortest - 1 and all(s[n] == stems[0][n] for s in stems):
        n += 1
    return n


def _derived_labels(files: Sequence[Path]) -> dict[Path, str]:
    stems = {f.stem for f in files}
    keyed = {s[: -len(KEY_SUFFIX)] for s in stems if s.endswith(KEY_SUFFIX)} & stems
    labels: dict[Path, str] = {}
    rest: list[Path] = []
    for f in files:
        if f.stem in keyed:
            labels[f] = "Sheet"
        elif f.stem.endswith(KEY_SUFFIX) and f.stem[: -len(KEY_SUFFIX)] in keyed:
            labels[f] = "Key"
        else:
            rest.append(f)
    distinct = sorted({f.stem for f in rest})
    if len(distinct) < 2:  # one name (one file, or one per kind): the name is the label
        labels.update({f: f.stem for f in rest})
        return labels
    tokens = {stem: stem.split("_") for stem in distinct}
    n = _common_prefix(list(tokens.values()))
    labels.update({f: _humanise(tokens[f.stem][n:]) for f in rest})
    return labels


def file_chips(files: Sequence[Path], labels: Mapping[Path, str] | None = None) -> list[FileChip]:
    """One chip per file, in kind order; ``labels`` overrides the derived names."""
    derived = _derived_labels(files)
    given = labels or {}
    chips = [FileChip(f, file_kind(f), given.get(f) or derived[f]) for f in dict.fromkeys(files)]
    order = {chip.path: i for i, chip in enumerate(chips)}
    return sorted(chips, key=lambda c: (KIND_ORDER.get(c.kind, len(KIND_ORDER)), order[c.path]))


def split_outcome(text: str) -> tuple[str, str]:
    """``("10 questions", "seed 42")`` from ``"10 questions · seed 42"``: the
    headline and the rest (empty when there is no separator)."""
    head, _sep, rest = text.partition(SEPARATOR)
    return head.strip(), rest.strip()


def warning_count(n: int) -> str:
    return f"{n} warning{'s' if n != 1 else ''}"
