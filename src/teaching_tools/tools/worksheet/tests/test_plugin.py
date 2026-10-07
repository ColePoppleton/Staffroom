from pathlib import Path

from typer.testing import CliRunner

from teaching_tools.cli import app
from teaching_tools.core.config import load_config
from teaching_tools.core.plugin import RunContext
from teaching_tools.tools.worksheet import plugin
from teaching_tools.tools.worksheet.logic import Options

runner = CliRunner()


def test_run_writes_sheet_and_key_with_seed_in_header(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    result = plugin.run(
        {"options": Options(topic="truth_tables", count=3, seed=11, formats="docx")}, ctx
    )
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "truth_tables_medium_s11.docx",
        "truth_tables_medium_s11_key.docx",
    ]
    preview = result.texts["preview"]
    assert "seed 11" in preview and "A  B  C  Q" in preview and "ANSWER KEY" in preview


def test_cli_make_and_topics(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "worksheet",
            "make",
            "--topic",
            "binary",
            "--count",
            "4",
            "--seed",
            "42",
            "-f",
            "pdf",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert "Worksheet: Binary, denary and hexadecimal" in r.output and "seed 42" in r.output
    assert (tmp_path / "binary_medium_s42.pdf").exists() and (
        tmp_path / "binary_medium_s42_key.pdf"
    ).exists()
    r = runner.invoke(app, ["worksheet", "topics"])
    assert r.exit_code == 0 and "huffman" in r.output
    r = runner.invoke(app, ["worksheet", "make", "--topic", "nope"])
    assert r.exit_code == 1
