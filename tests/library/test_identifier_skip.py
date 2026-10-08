"""At index time a searchable file whose text looks like pupil details is
stored by name only and counted. The fixture text is invented and holds no
names, even made-up ones."""

from __future__ import annotations

from pathlib import Path

from staffroom.core.library.model import IndexStats, withheld_message
from staffroom.core.library.service import LibraryService

LOOKS_PERSONAL = (
    "# GCSE Programming Task\n"
    "# Candidate number: 4021\n"
    "# UPN: A123456789012\n"
    "total = 0\nfor i in range(3):\n    total += i\n"
)
BLANK_TEMPLATE = (
    "# GCSE Programming Task\n# Candidate number: ________\n# Surname: ________\n"
    "# Date of birth: __/__/____\n"
    "print('template')\n"
)


def test_file_with_identifiers_is_indexed_by_name_only(
    resources_root: Path, tmp_path: Path
) -> None:
    (resources_root / "Python" / "task_submission.py").write_text(LOOKS_PERSONAL)
    (resources_root / "Python" / "task_template.py").write_text(BLANK_TEMPLATE)
    svc = LibraryService(resources_root, tmp_path / "library.db", opener=lambda a: None)
    stats = svc.index()

    assert stats.text_withheld == 1
    assert stats.withheld_paths == ["Python/task_submission.py"]
    assert "1 file skipped for text" in stats.summary()
    assert "pupil details" in stats.summary()

    withheld = svc.get("Python/task_submission.py")
    assert withheld is not None and withheld.text_withheld
    template = svc.get("Python/task_template.py")
    assert template is not None and not template.text_withheld

    # The name is searchable; the text is not in the database at all.
    assert "Python/task_submission.py" in [h.resource.rel_path for h in svc.search("submission")]
    assert svc.search("4021") == []
    assert svc.search("A123456789012") == []
    row = svc.db.conn.execute(
        "SELECT text FROM fts WHERE rel_path = ?", ("Python/task_submission.py",)
    ).fetchone()
    assert row["text"] == ""
    # ...while the blank template's text is indexed as normal.
    assert "Python/task_template.py" in [h.resource.rel_path for h in svc.search("template")]

    assert svc.withheld_count() == 1
    assert svc.withheld_paths() == ["Python/task_submission.py"]

    # Unchanged files keep their state across an incremental run.
    again = svc.index()
    assert again.text_withheld == 0 and svc.withheld_count() == 1


def test_withheld_message_wording() -> None:
    one = withheld_message(1)
    assert one.startswith("1 file skipped for text")
    assert "exclude the folder" in one.lower()
    assert withheld_message(3).startswith("3 files skipped for text")
    assert IndexStats().summary().count("\n") == 0
