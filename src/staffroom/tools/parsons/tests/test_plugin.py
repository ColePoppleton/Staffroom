from pathlib import Path

from docx import Document as DocxReader
from pypdf import PdfReader
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core import paths
from staffroom.core.config import load_config
from staffroom.core.export import render, to_text
from staffroom.core.plugin import RunContext
from staffroom.tools.parsons import plugin
from staffroom.tools.parsons.logic import Options, make_problem
from staffroom.tools.parsons.sheet import build_document

runner = CliRunner()
YEAR9 = paths.examples_dir() / "year9.py"
CODE = "count = 0\nwhile count < 10:\n    print(count)\n    count += 1\n"


def test_run_from_pasted_code_writes_sheet_and_key(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    result = plugin.run({"pasted": CODE, "options": Options(seed=5, distractors=1)}, ctx)
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [
        "pasted_code_parsons_s5.docx",
        "pasted_code_parsons_s5.pdf",
        "pasted_code_parsons_s5_key.docx",
        "pasted_code_parsons_s5_key.pdf",
    ]
    preview = result.texts["preview"]
    assert "Parsons problem: pasted_code" in preview and "Correct order:" in preview
    assert "Reconstructed program" in preview


def test_cli_make(tmp_path: Path) -> None:
    src = tmp_path / "loop.py"
    src.write_text(CODE)
    r = runner.invoke(
        app,
        [
            "parsons",
            "make",
            str(src),
            "--seed",
            "9",
            "-d",
            "2",
            "-f",
            "pdf",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert "Correct order:" in r.output and (tmp_path / "loop_parsons_s9_key.pdf").exists()
    bad = tmp_path / "bad.py"
    bad.write_text("while True\n  pass\n")
    r = runner.invoke(app, ["parsons", "make", str(bad), "--out", str(tmp_path)])
    assert r.exit_code == 1 and "not valid Python" in r.output


def test_year9_sheet_prints_on_one_page(tmp_path: Path) -> None:
    """The audit's measured failure (#22): twelve blocks and three distractors
    took two A4 pages with the answer grid on the second. Boxed cut-out
    blocks two across put it all on one."""
    options = Options(seed=7, distractors=3)
    problem = make_problem(YEAR9.read_text(), options)
    assert len(problem.solution) == 12 and len(problem.shuffled) == 15
    doc = build_document(problem, "year9", options)

    sheet = PdfReader(str(render(doc.sheet(), tmp_path / "sheet.pdf")))
    assert len(sheet.pages) == 1
    text = sheet.pages[0].extract_text()
    assert "Write the block numbers in order" in text and "cut them out" in text
    assert "15" in text and "average = total / count" in text

    key = PdfReader(str(render(doc.key(), tmp_path / "key.pdf")))
    assert "Correct order:" in key.pages[0].extract_text()

    read = DocxReader(str(render(doc.sheet(), tmp_path / "sheet.docx")))
    boxes = next(t for t in read.tables if t.cell(0, 0).text.startswith("1  "))
    assert len(boxes.columns) == 2 and len(boxes.rows) == 8
    preview = to_text(doc)
    assert "+- 1 " in preview and preview.count("[____]") == 12


def test_sheet_without_indentation_still_boxes_every_block() -> None:
    options = Options(seed=3, distractors=0, show_indentation=False, hint=False)
    problem = make_problem(YEAR9.read_text(), options)
    preview = to_text(build_document(problem, "year9", options))
    assert "Indentation has been removed" in preview
    assert '| print("Well done")' in preview  # dedented inside its box
