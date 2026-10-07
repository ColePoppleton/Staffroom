"""Acceptance: every variant differs from the original by exactly the
described mutation, and the key says what each one does."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from teaching_tools.cli import app
from teaching_tools.core.config import load_config
from teaching_tools.core.plugin import RunContext
from teaching_tools.tools.bugs import logic, plugin
from teaching_tools.tools.bugs.logic import KIND_LABELS, Options

runner = CliRunner()

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
