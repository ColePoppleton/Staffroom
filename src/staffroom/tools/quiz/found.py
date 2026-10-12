"""What quiz finds in its inputs while the teacher fills them in
(``PanelSpec.inspect``): the bank's summary and its questions for *Preview*,
its topics as chips with counts and the running total under them, what the
taught log says was taught 1, 3 and 6 weeks before the date, and the run
button's words. Files are read through :mod:`staffroom.tools.quiz.bank`
(the taught log through :func:`staffroom.core.csvio.read_table`); the
phrases are built by the pure helpers below."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from staffroom.core import spec
from staffroom.core.panel import ChipOption, Found, Inspection, Note
from staffroom.core.plugin import ToolError
from staffroom.tools.quiz import logic
from staffroom.tools.quiz.bank import load_taught_log, peek_bank
from staffroom.tools.quiz.panel import RUN_LABELS, options_from

BOARD_NAMES = {"ocr": "OCR", "aqa": "AQA"}
WEEKS = (1, 3, 6)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _and(items: Sequence[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def boards_phrase(bank: logic.Bank) -> str:
    """ "OCR and AQA spec points", "OCR spec points" or "no spec points"."""
    boards: dict[str, None] = {}
    for q in bank.questions:
        for tag in q.spec_tags:
            board = tag.partition(":")[0].lower()
            boards.setdefault(BOARD_NAMES.get(board, board.upper()), None)
    return f"{_and(list(boards))} spec points" if boards else "no spec points"


def bank_notes(bank: logic.Bank) -> tuple[Note, ...]:
    """The bank's summary line (*13 questions · 6 topics · OCR and AQA spec
    points · no problems*), then the first problem with its line, if any."""
    if not bank.questions:
        first = f" First problem: {bank.errors[0]}." if bank.errors else ""
        return (Note("No questions found: each starts with '## '." + first, ok=False),)
    unknown = sorted({t for q in bank.questions for t in q.spec_tags if spec.find(t) is None})
    problems = len(bank.errors) + len(unknown)
    parts = [
        _plural(len(bank.questions), "question"),
        _plural(len(bank.topics), "topic"),
        boards_phrase(bank),
        "no problems" if not problems else _plural(problems, "problem"),
    ]
    notes = [Note(" · ".join(parts), ok=not problems)]
    if bank.errors:
        more = len(bank.errors) - 1
        tail = f" (and {more} more: `staff quiz check` lists them)" if more else ""
        notes.append(Note(bank.errors[0][:1].upper() + bank.errors[0][1:] + tail, ok=False))
    if unknown:
        notes.append(Note(f"Not in the spec: {', '.join(unknown)}", ok=False))
    return tuple(notes)


def topic_chips(bank: logic.Bank) -> tuple[ChipOption, ...]:
    """The bank's topics in the order it first uses them, each with how many
    questions carry it."""
    counts = Counter(t for q in bank.questions for t in q.topics)
    return tuple(ChipOption(t, count=counts[t]) for t in bank.topics)


def _picked(pool: int, count: int) -> str:
    """How many of ``pool`` questions go on the sheet, after a " · "."""
    if pool <= 1:
        return ""
    return " · " + (f"all {pool} picked" if pool <= count else f"{count} of them picked")


def topics_total(bank: logic.Bank, options: logic.Options) -> Note:
    """The running total under the chips."""
    pool = logic.filter_questions(bank.questions, options.topics, options.spec)
    spec_part = f" with spec {options.spec}" if options.spec.strip() else ""
    if not options.topics:
        if not pool:
            return Note(f"No question{spec_part}.", ok=False)
        where = f"any of the {len(pool)} questions{spec_part}" if len(pool) > 1 else "the question"
        return Note(f"No topic picked: {where}{_picked(len(pool), options.count)}")
    if not pool:
        return Note(f"No question in the chosen topics{spec_part}.", ok=False)
    return Note(
        f"{_plural(len(pool), 'question')} in the chosen topics{spec_part}"
        f"{_picked(len(pool), options.count)}"
    )


def as_of_date(text: str, today: date | None = None) -> date:
    """The retrieval date: ``text`` (YYYY-MM-DD), today when blank. A
    ToolError for anything else."""
    if not text.strip():
        return today or date.today()
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise ToolError(
            f"The 'as of' date should look like 2026-10-08 (YYYY-MM-DD), not {text!r}."
        ) from None


def taught_notes(
    bank: logic.Bank | None,
    entries: list[logic.TaughtEntry],
    as_of: date,
    options: logic.Options,
) -> list[Note]:
    """What was taught in each window before ``as_of``, and how many of the
    bank's questions that leaves."""
    windows = logic.topics_in_windows(entries, as_of, WEEKS)
    parts = [f"{w} week{'s' if w > 1 else ''}: {', '.join(windows[w]) or 'nothing'}" for w in WEEKS]
    parts[0] = f"1 week before {as_of:%a} {as_of.day} {as_of:%b}" + parts[0][len("1 week") :]
    notes = [Note(" · ".join(parts))]
    if bank is None or not bank.questions:
        return notes
    taught = {t for topics in windows.values() for t in topics}
    if not taught:
        notes.append(Note("Nothing in the log falls in those weeks.", ok=False))
        return notes
    pool = logic.filter_questions(bank.questions, "", options.spec)
    eligible = [q for q in pool if any(t in taught for t in q.topics)]
    missing = sorted(taught - set(bank.topics))
    if eligible:
        notes.append(
            Note(
                f"{_plural(len(eligible), 'question')} in those topics"
                f"{_picked(len(eligible), options.count)}"
            )
        )
    else:
        notes.append(Note("No question in the bank is on those topics.", ok=False))
    if missing:
        notes.append(Note(f"Not in the bank: {', '.join(missing)}", ok=False))
    return notes


def _taught_found(log_path: Path, bank: logic.Bank | None, options: logic.Options) -> Found:
    try:
        table = load_taught_log(log_path)
        as_of = as_of_date(options.today)
    except ToolError as exc:
        return Found(notes=(Note(str(exc), ok=False),))
    entries, errors = logic.parse_taught_log(table)
    notes: list[Note] = []
    if table.dropped_columns:
        notes.append(
            Note("Never read: " + ", ".join(table.dropped_columns) + " (could name a pupil)", False)
        )
    notes.extend(taught_notes(bank, entries, as_of, options))
    if errors:
        more = f" (and {len(errors) - 1} more)" if len(errors) > 1 else ""
        notes.append(Note(errors[0][:1].upper() + errors[0][1:] + more, ok=False))
    return Found(notes=tuple(notes))


def inspect_inputs(inputs: Mapping[str, Any]) -> Inspection:
    """The panel's ``inspect``: see the module doc."""
    options = options_from(inputs)
    found: dict[str, Found] = {}
    bank: logic.Bank | None = None
    source = inputs.get("source")
    if isinstance(source, Path):
        try:
            bank = peek_bank(source)
        except ToolError as exc:
            found["source"] = Found(notes=(Note(str(exc), ok=False),))
        else:
            found["source"] = Found(
                notes=bank_notes(bank),
                rows=logic.selection_table(bank.questions) if bank.questions else None,
                rows_label="Preview questions",
            )
    if bank is not None and bank.questions:
        found["topics"] = Found(notes=(topics_total(bank, options),), chips=topic_chips(bank))
    else:
        found["topics"] = Found(chips=())
    log_path = inputs.get("taught_log")
    if options.retrieval and isinstance(log_path, Path):
        found["taught_log"] = _taught_found(log_path, bank, options)
    return Inspection(found=found, run_label=RUN_LABELS.get(options.fmt, ""))
