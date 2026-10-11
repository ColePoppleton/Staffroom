"""Acceptance: every variant differs from the original by exactly the
described mutation, and the key says what each one does."""

from pathlib import Path

import pytest
from pypdf import PdfReader
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core import paths
from staffroom.core.config import load_config
from staffroom.core.export import render, to_text
from staffroom.core.plugin import RunContext, RunResult, ToolError
from staffroom.core.runner import RunOutcome, run_source
from staffroom.tools.bugs import classify, logic, plugin, runs_the_same
from staffroom.tools.bugs.logic import KIND_LABELS, Options
from staffroom.tools.bugs.sheet import build_document

runner = CliRunner()
YEAR9 = paths.examples_dir() / "year9.py"

PROGRAM = """total = 0
count = 1
limit = 5
while count <= limit:
    total = total + count
    count = count + 1
for i in range(3):
    print(i)
score = int(input())
if score > 10:
    print("high")
else:
    print("low")
print(total)
"""


def test_candidates_cover_every_kind() -> None:
    kinds = {m.kind for m in logic.candidates(PROGRAM)}
    assert kinds == set(KIND_LABELS)


@pytest.mark.parametrize("seed", range(1, 12))
def test_each_variant_is_exactly_one_described_mutation(seed: int) -> None:
    options = Options(count=7, seed=seed)
    variants = logic.make_variants(PROGRAM, options)
    assert len(variants) == 7
    assert len({v.mutation.kind for v in variants}) == 7  # one of each kind first
    for v in variants:
        diff = logic.one_line_diff(PROGRAM, v.source)
        assert diff is not None, v.mutation
        line_no, old, new = diff
        assert (
            line_no == v.mutation.line and old == v.mutation.original and new == v.mutation.mutated
        )
        assert logic.describes(v.mutation, old, new), (v.mutation.kind, old, new)
    again = logic.make_variants(PROGRAM, options)
    assert [v.source for v in again] == [v.source for v in variants]


def test_kinds_can_be_restricted() -> None:
    options = Options(
        count=3,
        seed=2,
        comparison_flip=False,
        off_by_one=False,
        missing_colon=False,
        missing_bracket=False,
        wrong_variable=False,
        indentation_slip=False,
    )
    variants = logic.make_variants(PROGRAM, options)
    assert variants and all(v.mutation.kind == "string_int" for v in variants)


def test_plugin_runs_variants_and_classifies(tmp_path: Path) -> None:
    logs: list[str] = []
    ctx = RunContext(config=load_config(), output_dir=tmp_path, log=logs.append)
    result = plugin.run(
        {"pasted": PROGRAM, "stdin": "7\n", "options": Options(count=7, seed=3, formats="pdf")}, ctx
    )
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names[:7] == [f"pasted_code_bug{i}.py" for i in range(1, 8)]
    assert "pasted_code_bugs.pdf" in names and "pasted_code_bugs_key.pdf" in names
    outcomes = [str(row[5]) for row in result.tables["key"].rows]
    assert any(o.startswith("crashes") for o in outcomes)
    assert any("output is wrong" in o or "no visible change" in o for o in outcomes)
    for v, row in zip(
        logic.make_variants(PROGRAM, Options(count=7, seed=3)),
        result.tables["key"].rows,
        strict=True,
    ):
        assert (tmp_path / f"pasted_code_bug{row[0]}.py").read_text() == v.source


def test_cli(tmp_path: Path) -> None:
    src = tmp_path / "prog.py"
    src.write_text(PROGRAM)
    r = runner.invoke(
        app,
        [
            "bugs",
            "make",
            str(src),
            "-n",
            "3",
            "--stdin",
            "7",
            "--kinds",
            "missing_colon,off_by_one",
            "-f",
            "docx",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert (
        "line" in r.output
        and (tmp_path / "prog_bug1.py").exists()
        and (tmp_path / "prog_bugs_key.docx").exists()
    )
    r = runner.invoke(app, ["bugs", "kinds"])
    assert r.exit_code == 0 and "indentation_slip" in r.output
    r = runner.invoke(app, ["bugs", "make", str(src), "--kinds", "nope"])
    assert r.exit_code == 1


def test_classify_says_when_a_variant_prints_past_the_cap() -> None:
    original = RunOutcome(stdout="1\n", returncode=0)
    flood = RunOutcome(stdout="1\n1\n", returncode=0, stdout_truncated=True)
    assert classify(original, flood) == "runs, but the output is wrong; output capped at 1024 KB"
    assert classify(original, RunOutcome(stdout="1\n", returncode=0)).startswith("silent")


def _pages(doc_variants: int, tmp_path: Path) -> int:
    source = YEAR9.read_text()
    variants = logic.make_variants(source, Options(count=doc_variants, seed=1))
    assert len(variants) == doc_variants
    doc = build_document("year9", source, variants)
    path = render(doc.sheet(), tmp_path / f"bugs{doc_variants}.pdf")
    return len(PdfReader(str(path)).pages)


def test_two_variants_per_printed_page(tmp_path: Path) -> None:
    """The audit's measured failure (#22): four 13-line variants printed on
    four pages. Two per page, with the answer line under each."""
    assert _pages(4, tmp_path) == 2
    assert _pages(1, tmp_path) == 1
    assert _pages(5, tmp_path) == 3


def test_page_break_only_between_pairs() -> None:
    source = YEAR9.read_text()
    variants = logic.make_variants(source, Options(count=4, seed=1))
    text = to_text(build_document("year9", source, variants))
    assert text.count("page break") == 1
    v1 = text.index("Version 1")
    v2 = text.index("Version 2")
    assert text.index("Line: ______", v1) < v2  # the answer line sits under its version
    assert text.index("page break") > text.index("Line: ______", v2)


# ---------------------------------------------------------------- #92: bugs a pupil can see
def _run(
    tmp_path: Path, options: Options, source: Path | None = None
) -> tuple[RunResult, list[str], list[str]]:
    logs: list[str] = []
    warnings: list[str] = []
    ctx = RunContext(
        config=load_config(), output_dir=tmp_path, log=logs.append, warned=warnings.append
    )
    result = plugin.run({"source": source or YEAR9, "options": options}, ctx)
    return result, logs, warnings


def test_default_year9_variants_all_change_behaviour(tmp_path: Path) -> None:
    """The audit's measured failure: at the defaults two of four year9 variants
    ran exactly like the original. Now all four change what a pupil sees."""
    result, logs, warnings = _run(tmp_path, Options(formats="pdf"))
    rows = result.tables["key"].rows
    assert len(rows) == 4
    assert not any("silent" in str(row[5]) for row in rows)
    original = run_source(YEAR9.read_text())
    for row in rows:
        variant = run_source((tmp_path / f"year9_bug{row[0]}.py").read_text())
        assert not runs_the_same(original, variant), row
    assert not warnings
    assert any(line.startswith("Skipped line 9") for line in logs)  # the two silent ones
    sheet = result.texts["preview"]
    assert "read the code" not in sheet and "(crash or wrong output)" in sheet
    assert "seed 1" in result.outcome


def test_same_seed_same_variants(tmp_path: Path) -> None:
    first, _, _ = _run(tmp_path / "a", Options(seed=5, formats="pdf"))
    second, _, _ = _run(tmp_path / "b", Options(seed=5, formats="pdf"))
    assert first.tables["key"].rows == second.tables["key"].rows


def test_kept_silent_variant_is_labelled(tmp_path: Path) -> None:
    result, _, warnings = _run(tmp_path, Options(silent=1, formats="pdf"))
    rows = result.tables["key"].rows
    silent = [row for row in rows if str(row[5]).startswith("silent")]
    assert len(rows) == 4 and len(silent) == 1
    sheet = result.texts["preview"]
    assert f"Version {silent[0][0]} (this version may run the same: read the code)" in sheet
    assert sheet.count("read the code") == 1
    assert "1 silent" in result.outcome
    assert any("runs exactly like the original" in w for w in warnings)


def test_says_when_fewer_visible_bugs_are_possible(tmp_path: Path) -> None:
    result, _, warnings = _run(tmp_path, Options(count=20, formats="pdf"))
    rows = result.tables["key"].rows
    assert 0 < len(rows) < 20
    assert not any("silent" in str(row[5]) for row in rows)
    assert any(f"Only {len(rows)} distinct bugs change" in w for w in warnings), warnings
    assert "(asked for 20)" in result.outcome


def test_every_bug_silent_is_a_teacher_error(tmp_path: Path) -> None:
    src = tmp_path / "quiet.py"
    src.write_text('x = 1\nif x > 5:\n    print("big")\n')
    only_flips = Options(
        formats="pdf",
        off_by_one=False,
        missing_colon=False,
        missing_bracket=False,
        wrong_variable=False,
        indentation_slip=False,
        string_int=False,
    )
    with pytest.raises(ToolError, match="Silent bugs allowed"):
        _run(tmp_path / "out", only_flips, src)
    only_flips.silent = 1
    result, _, _ = _run(tmp_path / "out", only_flips, src)
    assert str(result.tables["key"].rows[0][5]).startswith("silent")


def test_choose_skips_silent_candidates_in_seed_order() -> None:
    every = logic.choose(PROGRAM, 30, list(KIND_LABELS), seed=4)
    quiet = {m for m in every if m.kind in ("comparison_flip", "off_by_one")}
    asked: list[logic.Mutation] = []

    def changes(m: logic.Mutation) -> bool:
        asked.append(m)
        return m not in quiet

    picked = logic.choose(PROGRAM, 4, list(KIND_LABELS), 4, changes)
    assert len(picked) == 4 and not quiet & set(picked)
    assert len(asked) == len(set(asked))  # each candidate is run at most once
    assert logic.choose(PROGRAM, 4, list(KIND_LABELS), 4, changes) == picked  # reproducible
    kept_one = logic.choose(PROGRAM, 4, list(KIND_LABELS), 4, changes, silent=1)
    assert len(quiet & set(kept_one)) == 1
    # Allowing as many silent ones as variants is the old, unchecked choice.
    assert logic.choose(PROGRAM, 4, list(KIND_LABELS), 4, changes, silent=4) == logic.choose(
        PROGRAM, 4, list(KIND_LABELS), 4
    )


def test_same_crash_as_a_crashing_original_is_silent() -> None:
    boom = RunOutcome(stdout="a\n", stderr="ZeroDivisionError: division by zero", returncode=1)
    assert runs_the_same(boom, boom)
    assert classify(boom, boom).startswith("silent")
    other = RunOutcome(stdout="a\n", stderr="NameError: name 'x' is not defined", returncode=1)
    assert classify(boom, other) == "crashes: NameError"
