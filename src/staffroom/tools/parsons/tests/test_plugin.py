from pathlib import Path

from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext
from staffroom.tools.parsons import plugin
from staffroom.tools.parsons.logic import Options

runner = CliRunner()
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
