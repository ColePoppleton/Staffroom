"""Pure logic for quiz: parse a Markdown question bank, select questions,
export to Kahoot / Forms text / do-now rows, and schedule retrieval. No I/O.

Bank format (Markdown)::

    # Any title line is ignored
    ## What does CPU stand for?
    type: mcq
    tags: ocr:1.1.1, aqa:3.4.4, topic:cpu
    time: 20
    - [x] Central Processing Unit
    - [ ] Central Program Utility
    - [ ] Computer Personal Unit
    - [ ] Core Processing Utility
    why: The CPU fetches, decodes and executes instructions.

    ## RAM is volatile.
    type: tf
    tags: topic:memory
    answer: true

    ## What is 1010 in denary?
    type: short
    tags: ocr:1.2.4, topic:binary
    answer: 10
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

from staffroom.core.table import Row, Table

QType = Literal["mcq", "short", "tf"]
Format = Literal["kahoot", "forms", "donow"]
KAHOOT_TIMES = (5, 10, 20, 30, 60, 90, 120, 240)
KAHOOT_QUESTION_MAX = 120
KAHOOT_ANSWER_MAX = 75
KAHOOT_HEADERS = (
    "Question - max 120 characters",
    "Answer 1 - max 75 characters",
    "Answer 2 - max 75 characters",
    "Answer 3 - max 75 characters",
    "Answer 4 - max 75 characters",
    "Time limit (sec) – 5, 10, 20, 30, 60, 90, 120, or 240 secs",
    "Correct answer(s) - choose at least one",
)


@dataclass
class Options:
    # Do-now first: the weekly use, checked on paper; Kahoot's import is
    # still to be confirmed (#1). The CLI's ``export --format`` keeps its own.
    fmt: Format = field(default="donow", metadata={"label": "Format"})
    count: int = field(default=10, metadata={"label": "Questions", "min": 1, "max": 100})
    seed: int = field(default=1, metadata={"label": "Seed", "min": 0, "max": 999_999})
    topics: str = field(
        default="", metadata={"label": "Topics", "help": "Comma-separated topic tags; empty = any"}
    )
    spec: str = field(
        default="",
        metadata={"label": "Spec points", "help": "e.g. ocr:1.2 or aqa:3.3.4; prefixes match"},
    )
    retrieval: bool = field(
        default=False,
        metadata={
            "label": "Retrieval mode",
            "help": "Pick from topics taught 1, 3 and 6 weeks ago",
        },
    )
    today: str = field(
        default="",
        metadata={"label": "As of (YYYY-MM-DD)", "help": "Retrieval date; empty = today"},
    )
    title: str = field(default="Do now", metadata={"label": "Title"})


@dataclass(frozen=True)
class Question:
    number: int
    text: str
    qtype: QType
    options: tuple[str, ...] = ()
    correct: tuple[int, ...] = ()  # indexes into options (mcq)
    answer: str = ""  # short / tf
    tags: tuple[str, ...] = ()
    time: int = 20
    why: str = ""

    @property
    def topics(self) -> tuple[str, ...]:
        return tuple(t[6:] for t in self.tags if t.startswith("topic:"))

    @property
    def spec_tags(self) -> tuple[str, ...]:
        return tuple(t for t in self.tags if not t.startswith("topic:"))

    @property
    def answer_text(self) -> str:
        if self.qtype == "mcq":
            return "; ".join(self.options[i] for i in self.correct)
        return self.answer


@dataclass
class Bank:
    questions: list[Question]
    errors: list[str]
    title: str = ""

    @property
    def topics(self) -> list[str]:
        seen: dict[str, None] = {}
        for q in self.questions:
            for t in q.topics:
                seen.setdefault(t, None)
        return list(seen)


# ---------------------------------------------------------------- parsing
_OPTION = re.compile(r"^-\s*\[( |x|X)\]\s*(.+)$")
_FIELD = re.compile(r"^(type|tags|answer|time|why|explanation)\s*:\s*(.*)$", re.I)


def parse_bank(text: str) -> Bank:
    questions: list[Question] = []
    errors: list[str] = []
    title = ""
    current: dict[str, object] | None = None
    start_line = 0

    def finish() -> None:
        nonlocal current
        if current is None:
            return
        q, errs = _build(current, start_line, len(questions) + 1)
        errors.extend(errs)
        if q is not None:
            questions.append(q)
        current = None

    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            finish()
            current = {"text": line[3:].removeprefix("Q:").strip(), "options": [], "correct": []}
            start_line = n
            continue
        if line.startswith("# "):
            if not title:
                title = line[2:].strip()
            continue
        if current is None:
            if not line.startswith(("<!--", "---")):
                errors.append(f"line {n}: text before the first '## ' question: {line}")
            continue
        m = _OPTION.match(line)
        if m:
            options = current["options"]
            assert isinstance(options, list)
            correct = current["correct"]
            assert isinstance(correct, list)
            if m.group(1).lower() == "x":
                correct.append(len(options))
            options.append(m.group(2).strip())
            continue
        f = _FIELD.match(line)
        if f:
            key = f.group(1).lower()
            current["why" if key == "explanation" else key] = f.group(2).strip()
            continue
        current["text"] = f"{current['text']} {line}".strip()
    finish()
    return Bank(questions, errors, title)


def _build(d: dict[str, object], line: int, number: int) -> tuple[Question | None, list[str]]:
    errors: list[str] = []
    text = str(d.get("text", "")).strip()
    options = list(d.get("options", []))  # type: ignore[call-overload]
    correct = list(d.get("correct", []))  # type: ignore[call-overload]
    qtype_raw = str(d.get("type", "")).lower() or ("mcq" if options else "short")
    tags = tuple(t.strip().lower() for t in str(d.get("tags", "")).split(",") if t.strip())
    time_raw = str(d.get("time", "20"))
    try:
        time = int(time_raw)
    except ValueError:
        errors.append(f"line {line}: time must be a number, got {time_raw!r}")
        time = 20
    answer = str(d.get("answer", "")).strip()
    why = str(d.get("why", "")).strip()
    if not text:
        errors.append(f"line {line}: question has no text")
        return None, errors
    if qtype_raw not in ("mcq", "short", "tf"):
        errors.append(f"line {line}: type must be mcq, short or tf, got {qtype_raw!r}")
        return None, errors
    qtype: QType = qtype_raw  # type: ignore[assignment]
    if qtype == "mcq":
        if len(options) < 2:
            errors.append(f"line {line}: an mcq needs at least two '- [ ]' options")
            return None, errors
        if not correct:
            errors.append(f"line {line}: an mcq needs at least one '- [x]' option")
            return None, errors
        return Question(
            number, text, "mcq", tuple(options), tuple(correct), "", tags, time, why
        ), errors
    if qtype == "tf":
        if answer.lower() not in ("true", "false"):
            errors.append(f"line {line}: a tf question needs 'answer: true' or 'answer: false'")
            return None, errors
        return Question(
            number,
            text,
            "tf",
            ("True", "False"),
            (0 if answer.lower() == "true" else 1,),
            answer.capitalize(),
            tags,
            time,
            why,
        ), errors
    if not answer:
        errors.append(f"line {line}: a short question needs 'answer: ...'")
        return None, errors
    return Question(number, text, "short", (), (), answer, tags, time, why), errors


# ---------------------------------------------------------------- selection
def _split(text: str) -> list[str]:
    return [t.strip().lower() for t in text.split(",") if t.strip()]


def filter_questions(questions: list[Question], topics: str = "", spec: str = "") -> list[Question]:
    wanted_topics = _split(topics)
    wanted_spec = _split(spec)
    out: list[Question] = []
    for q in questions:
        if wanted_topics and not any(t in wanted_topics for t in q.topics):
            continue
        if wanted_spec and not any(_spec_match(tag, w) for tag in q.spec_tags for w in wanted_spec):
            continue
        out.append(q)
    return out


def _spec_match(tag: str, wanted: str) -> bool:
    return tag == wanted or tag.startswith(wanted + ".")


def choose(questions: list[Question], count: int, seed: int) -> list[Question]:
    rng = random.Random(seed)
    pool = list(questions)
    rng.shuffle(pool)
    return sorted(pool[:count], key=lambda q: q.number)


def output_stem(bank_stem: str, options: Options, as_of: date | None = None) -> str:
    """The file stem for one run, so different kinds of sheet never share a name.

    An export is ``<bank>_<format>_s<seed>`` (``question_bank_donow_s1``); a
    retrieval run adds the date it was picked for,
    ``<bank>_retrieval_<YYYY-MM-DD>_<format>_s<seed>``. The seed is last, as on
    worksheets, and the same bank, kind, date, format and seed always give the
    same name: that is a regenerated sheet, and it replaces the earlier one."""
    kind = f"retrieval_{(as_of or date.today()).isoformat()}_" if options.retrieval else ""
    return f"{bank_stem}_{kind}{options.fmt}_s{options.seed}"


# ---------------------------------------------------------------- retrieval
@dataclass(frozen=True)
class TaughtEntry:
    day: date
    topic: str


def parse_taught_log(table: Table) -> tuple[list[TaughtEntry], list[str]]:
    """A table with ``date`` and ``topic`` columns (any order, any case), as
    read by :func:`staffroom.core.csvio.read_table`: the fake-data marker is
    already stripped and identifier-looking columns (a name, a class) are
    already dropped, so they never reach this function. Any other surviving
    column is ignored and named in the messages, once, by its header only: the
    log is date and topic, so whatever such a column holds is never read back.
    Messages count lines as the header being line 1."""
    entries: list[TaughtEntry] = []
    errors: list[str] = []
    if not table.columns:
        return entries, ["taught log is empty"]
    header = [h.strip().lower() for h in table.columns]
    if "date" not in header or "topic" not in header:
        return entries, ["taught log needs 'date' and 'topic' columns"]
    date_col, topic_col = header.index("date"), header.index("topic")
    for n, (raw, name) in enumerate(zip(table.columns, header, strict=True), 1):
        if n - 1 in (date_col, topic_col):
            continue
        what = f"column {raw.strip()!r}" if name else f"unnamed column {n}"
        errors.append(f"ignored {what} — the log is date and topic only")
    for i, row in enumerate(table.rows, 2):
        day_text = _cell_text(row[date_col])
        topic = _cell_text(row[topic_col])
        try:
            # datetime also takes an Excel date cell ("2026-09-17 00:00:00").
            day = datetime.fromisoformat(day_text).date()
        except ValueError:
            errors.append(f"line {i}: bad date {day_text!r} (use YYYY-MM-DD)")
            continue
        if not topic:
            errors.append(f"line {i}: missing topic")
            continue
        entries.append(TaughtEntry(day, topic.lower()))
    return entries, errors


def _cell_text(cell: object) -> str:
    return "" if cell is None else str(cell).strip()


def topics_in_windows(
    log: list[TaughtEntry],
    today: date,
    weeks: tuple[int, ...] = (1, 3, 6),
    tolerance_days: int = 3,
) -> dict[int, list[str]]:
    """Topics taught ``weeks`` ago (± tolerance), keyed by week."""
    out: dict[int, list[str]] = {}
    for w in weeks:
        target = today - timedelta(weeks=w)
        hits: list[str] = []
        for e in log:
            if abs((e.day - target).days) <= tolerance_days and e.topic not in hits:
                hits.append(e.topic)
        out[w] = hits
    return out


def retrieval_pick(
    questions: list[Question],
    log: list[TaughtEntry],
    today: date,
    count: int,
    seed: int,
    weeks: tuple[int, ...] = (1, 3, 6),
    tolerance_days: int = 3,
) -> tuple[list[Question], dict[int, list[str]]]:
    """Round-robin across the windows so each gets a fair share; only
    questions whose topics were taught in a window are eligible."""
    windows = topics_in_windows(log, today, weeks, tolerance_days)
    rng = random.Random(seed)
    pools: list[list[Question]] = []
    for w in weeks:
        pool = [q for q in questions if any(t in windows[w] for t in q.topics)]
        rng.shuffle(pool)
        pools.append(pool)
    chosen: list[Question] = []
    while len(chosen) < count and any(pools):
        for pool in pools:
            while pool:
                q = pool.pop()
                if q not in chosen:
                    chosen.append(q)
                    break
            if len(chosen) >= count:
                break
    return sorted(chosen, key=lambda q: q.number), windows


# ---------------------------------------------------------------- exporters
def _clip(text: str, limit: int, notes: list[str], what: str) -> str:
    if len(text) <= limit:
        return text
    notes.append(f"{what} clipped to {limit} characters: {text[:30]}…")
    return text[: limit - 1] + "…"


def _kahoot_time(seconds: int) -> int:
    return min(KAHOOT_TIMES, key=lambda t: (abs(t - seconds), t))


@dataclass
class KahootSheet:
    """What a Kahoot export holds: the rows in template order (no header),
    the questions those rows came from, the ones left out with the reason,
    and notes for the run log."""

    rows: list[list[str]] = field(default_factory=list)
    written: tuple[Question, ...] = ()
    skipped: tuple[tuple[Question, str], ...] = ()
    notes: list[str] = field(default_factory=list)


def _spec_sections(q: Question) -> set[str]:
    """``ocr:1.2.4`` → ``ocr:1.2``: the section a spec point sits in."""
    return {t.rsplit(".", 1)[0] for t in q.spec_tags}


def _describe(q: Question) -> str:
    return ", ".join(q.topics) or ", ".join(q.spec_tags) or "untagged"


def _distractors(
    q: Question, pool: list[Question], rng: random.Random
) -> list[tuple[str, Question]]:
    """Up to three distinct wrong answers for a short question, borrowed from
    other short answers in ``pool``: same topic first, then the same spec
    section, then anywhere. Returns ``(answer, donor)`` pairs."""
    donors = [d for d in pool if d.qtype == "short" and d is not q and d.answer.strip()]
    rng.shuffle(donors)

    def rank(d: Question) -> int:
        if set(d.topics) & set(q.topics):
            return 0
        if _spec_sections(d) & _spec_sections(q):
            return 1
        return 2

    donors.sort(key=rank)  # stable, so the shuffle decides ties within a tier
    taken = {q.answer.strip().casefold()}
    out: list[tuple[str, Question]] = []
    for d in donors:
        key = d.answer.strip().casefold()
        if key in taken:
            continue
        taken.add(key)
        out.append((d.answer.strip(), d))
        if len(out) == 3:
            break
    return out


def kahoot_sheet(questions: list[Question], pool: list[Question] | None = None) -> KahootSheet:
    """Build the Kahoot rows for ``questions``. A short-answer question needs
    three distractors, borrowed from the short answers in ``pool`` (the whole
    bank; defaults to ``questions``) nearest first: same topic, same spec
    section, then anywhere, with a note naming the source whenever a
    distractor came from outside the question's topic."""
    pool = list(pool) if pool is not None else list(questions)
    sheet = KahootSheet()
    notes = sheet.notes
    written: list[Question] = []
    skipped: list[tuple[Question, str]] = []
    for q in questions:
        if q.qtype == "short":
            rng = random.Random(q.number)
            borrowed = _distractors(q, pool, rng)
            if len(borrowed) < 3:
                reason = (
                    "short answer with too few distractors (needs 3 other short answers in the "
                    f"bank with different answers, found {len(borrowed)})"
                )
                notes.append(f"Q{q.number} skipped for Kahoot: {reason}")
                skipped.append((q, reason))
                continue
            outside = [(a, d) for a, d in borrowed if not (set(d.topics) & set(q.topics))]
            if outside:
                sources = ", ".join(f"'{a}' (Q{d.number}, {_describe(d)})" for a, d in outside)
                where = f"outside topic '{q.topics[0]}'" if q.topics else "from other topics"
                notes.append(f"Q{q.number}: distractors borrowed {where}: {sources}")
            options = [q.answer, *(a for a, _ in borrowed)]
            rng.shuffle(options)
            correct = [options.index(q.answer) + 1]
        else:
            options = list(q.options[:4])
            if len(q.options) > 4:
                notes.append(f"Q{q.number}: Kahoot allows 4 answers; extra options dropped")
            correct = [i + 1 for i in q.correct if i < 4]
            if not correct:
                reason = "no correct answer in the first 4 options"
                notes.append(f"Q{q.number} skipped for Kahoot: {reason}")
                skipped.append((q, reason))
                continue
        while len(options) < 4:
            options.append("")
        sheet.rows.append(
            [
                _clip(q.text, KAHOOT_QUESTION_MAX, notes, f"Q{q.number} text"),
                *(_clip(o, KAHOOT_ANSWER_MAX, notes, f"Q{q.number} answer") for o in options),
                str(_kahoot_time(q.time)),
                ",".join(str(c) for c in correct),
            ]
        )
        written.append(q)
    sheet.written = tuple(written)
    sheet.skipped = tuple(skipped)
    return sheet


def kahoot_report(sheet: KahootSheet, chosen: int) -> str:
    """The summary's opening phrase: ``"5 questions"`` when every chosen
    question was written, else ``"3 of 5 written; 2 short answers skipped: Q5, Q7"``."""
    if not sheet.skipped:
        return f"{chosen} question{'s' if chosen != 1 else ''}"
    n = len(sheet.skipped)
    names = ", ".join(f"Q{q.number}" for q, _ in sheet.skipped)
    if all(q.qtype == "short" for q, _ in sheet.skipped):
        what = f"{n} short answer{'s' if n != 1 else ''} skipped"
    else:
        what = f"{n} skipped"
    return f"{len(sheet.written)} of {chosen} written; {what}: {names}"


def _csv_field(value: str) -> str:
    if any(ch in value for ch in ',"\n\r'):
        return '"' + value.replace('"', '""') + '"'
    return value


def kahoot_csv(rows: list[list[str]]) -> str:
    lines = [",".join(_csv_field(h) for h in KAHOOT_HEADERS)]
    lines += [",".join(_csv_field(v) for v in row) for row in rows]
    return "\r\n".join(lines) + "\r\n"


def forms_text(questions: list[Question], title: str) -> str:
    """Plain text to paste into a Forms quiz, answers in a separate block."""
    lines: list[str] = [title, ""]
    for i, q in enumerate(questions, 1):
        lines.append(f"{i}. {q.text}")
        if q.qtype in ("mcq", "tf"):
            for j, opt in enumerate(q.options):
                lines.append(f"   {chr(65 + j)}) {opt}")
        lines.append("")
    lines += ["Answers", ""]
    for i, q in enumerate(questions, 1):
        if q.qtype in ("mcq", "tf"):
            letters = ", ".join(chr(65 + c) for c in q.correct)
            lines.append(f"{i}. {letters}")
        else:
            lines.append(f"{i}. {q.answer}")
    return "\n".join(lines) + "\n"


def selection_table(questions: list[Question]) -> Table:
    rows: list[Row] = [
        [q.number, q.qtype, q.text, ", ".join(q.topics), ", ".join(q.spec_tags), q.answer_text]
        for q in questions
    ]
    return Table(["#", "Type", "Question", "Topics", "Spec", "Answer"], rows)


def question_list(questions: list[Question]) -> Table:
    """The chosen questions as the panel lists them: numbered as on the sheet,
    the question, and its topics and type (*cpu · mcq*). The answers are on
    the key; the full row is :func:`selection_table` (the CLI's listing)."""
    rows: list[Row] = [
        [i, q.text, " · ".join((*q.topics, q.qtype))] for i, q in enumerate(questions, 1)
    ]
    return Table(["#", "Question", "Topic · type"], rows)
