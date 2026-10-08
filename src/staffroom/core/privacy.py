"""No pupil data, ever.

This module is the enforcement point for the project's hard rule: any table
loaded through :mod:`staffroom.core.csvio` passes through
:func:`drop_identifier_columns`, so a column that could identify a pupil never
reaches a tool, a preview or an output file. Tools cannot opt out.

What counts as an identifier is deliberately broad: names, ids, UPNs,
candidate numbers, emails, class/form/tutor groups, admission numbers, dates
of birth, and the obvious spellings and joined forms of each.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from staffroom.core.table import Table

# A column is an identifier if any whole word of its header is one of these...
IDENTIFIER_WORDS: frozenset[str] = frozenset(
    {
        "name",
        "names",
        "forename",
        "forenames",
        "surname",
        "surnames",
        "firstname",
        "lastname",
        "fullname",
        "nickname",
        "initials",
        "pupil",
        "pupils",
        "student",
        "students",
        "learner",
        "learners",
        "child",
        "id",
        "ids",
        "identifier",
        "upn",
        "uln",
        "adno",
        "admission",
        "candidate",
        "candidates",
        "cand",
        "email",
        "emails",
        "mail",
        "class",
        "classes",
        "form",
        "tutor",
        "tutorgroup",
        "formgroup",
        "set",
        "group",
        "dob",
        "birth",
        "birthday",
        "username",
        "login",
        "photo",
    }
)

# ...or if the whole header, with spaces and punctuation removed, is one of these.
JOINED_FORMS: frozenset[str] = frozenset(
    {
        "studentid",
        "pupilid",
        "learnerid",
        "candidateno",
        "candidatenumber",
        "candidateid",
        "candno",
        "emailaddress",
        "admissionno",
        "admissionnumber",
        "dateofbirth",
        "classname",
        "classcode",
        "teachinggroup",
        "regroup",
        "reggroup",
        "pupilname",
        "studentname",
        "learnername",
        "firstname",
        "lastname",
        "fullname",
        "surnameforename",
        "forenamesurname",
    }
)

_SPLIT = re.compile(r"[^a-z0-9]+")
_CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _words(header: str) -> list[str]:
    spaced = _CAMEL.sub(" ", header)
    return [w for w in _SPLIT.split(spaced.lower()) if w]


def is_identifier_column(header: str) -> bool:
    """``"Candidate Number"``, ``"studentId"``, ``"Class"`` -> True;
    ``"q1"``, ``"Total"``, ``"classwork"`` -> False."""
    words = _words(header)
    if not words:
        return False
    if any(w in IDENTIFIER_WORDS for w in words):
        return True
    joined = "".join(words)
    return joined in JOINED_FORMS


def identifier_columns(headers: Iterable[str]) -> list[str]:
    return [h for h in headers if is_identifier_column(h)]


def drop_identifier_columns(table: Table) -> tuple[Table, list[str]]:
    """Return ``(clean_table, dropped_column_names)``. The original is untouched."""
    dropped = identifier_columns(table.columns)
    if not dropped:
        return table, []
    keep = [c for c in table.columns if c not in dropped]
    clean = table.select(keep)
    clean.dropped_columns = [*table.dropped_columns, *dropped]
    return clean, dropped
