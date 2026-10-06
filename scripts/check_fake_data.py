#!/usr/bin/env python
"""Pre-commit hook: refuse staged CSV/XLSX files that lack the fake-data marker.

Real pupil data must never enter the repository. A CSV must start with a line
beginning ``# FAKE DATA``; an XLSX must contain ``FAKE DATA`` in a cell within
the first three rows of some sheet. See ``teaching_tools.core.csvio``.
"""

from __future__ import annotations

import sys
from pathlib import Path

from teaching_tools.core.csvio import FAKE_DATA_MARKER, has_fake_data_marker


def main(argv: list[str]) -> int:
    bad: list[Path] = []
    for arg in argv:
        path = Path(arg)
        if not path.exists():
            continue
        try:
            ok = has_fake_data_marker(path)
        except Exception as exc:  # unreadable file: refuse, do not guess
            print(f"{path}: could not inspect ({exc})")
            ok = False
        if not ok:
            bad.append(path)
    if bad:
        print("Refusing to commit data files without a fake-data marker:")
        for path in bad:
            print(f"  {path}")
        print(
            f"\nIf this really is invented data, add a first row '{FAKE_DATA_MARKER}' (CSV) "
            "or a cell containing 'FAKE DATA' in the first rows (XLSX).\n"
            "If it is real pupil data, keep it in data/ (git-ignored), never in the repo."
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
