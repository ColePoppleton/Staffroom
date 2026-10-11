"""The date printed in every sheet's header.

A teacher's sheet carries the day it was made. Renders that must not change
from one day to the next (the docs screenshots, ``scripts/screenshots.sh``)
set ``STAFFROOM_DATE=YYYY-MM-DD`` and every sheet carries that day instead.

This is the only place the variable is read. Sheet builders take the date as
an argument and fall back to :func:`sheet_date`; tool logic never sees it.
It is only what a sheet prints, never where a file goes: the day Classroom's
session folder is named after is today, and a screenshot pins only the day the
panel *shows* with ``staffroom --screenshot --today`` (#116).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import date

DATE_ENV = "STAFFROOM_DATE"


def sheet_date(environ: Mapping[str, str] | None = None) -> date:
    """``STAFFROOM_DATE`` when it is set, today otherwise. A value that is not
    ``YYYY-MM-DD`` is refused rather than silently replaced by today, so a
    reproducible render cannot quietly stop being reproducible."""
    text = (os.environ if environ is None else environ).get(DATE_ENV, "").strip()
    if not text:
        return date.today()
    try:
        return date.fromisoformat(text)
    except ValueError:
        msg = f"{DATE_ENV} should be a date like 2026-10-09 (YYYY-MM-DD), not {text!r}"
        raise ValueError(msg) from None
