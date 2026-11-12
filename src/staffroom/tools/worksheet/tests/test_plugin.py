import re
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import Config, GeneralSettings, load_config
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.worksheet import plugin
from staffroom.tools.worksheet.logic import Options

runner = CliRunner()


def _run(tmp_path: Path, lesson: str, board: str = "ocr", **inputs: Any) -> str:
    cfg = Config(general=GeneralSettings(board=board), path=tmp_path / "config.toml")
    ctx = RunContext(config=cfg, output_dir=tmp_path / "out")
    options = inputs.pop("options", Options(count=3, seed=11, formats="docx"))
    result = plugin.run({"lesson": lesson, "options": options, **inputs}, ctx)
    return result.texts["preview"]


def test_review_writes_the_old_files_with_seed_in_header(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    options = Options(count=3, seed=11, formats="docx")
    result = plugin.run({"lesson": "logic/review-truth-tables", "options": options}, ctx)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "truth_tables_medium_s11.docx",
        "truth_tables_medium_s11_key.docx",
    ]
    preview = result.texts["preview"]
    assert "seed 11" in preview and "A  B  C  Q" in preview and "ANSWER KEY" in preview
    assert "gates: AND, OR, NOT" in preview  # the default board is OCR


def test_lesson_sheet_has_aim_example_sections_and_spec_point(tmp_path: Path) -> None:
    options = Options(count=10, seed=42, formats="pdf")
    text = _run(tmp_path, "binary/denary-to-binary", board="edexcel", options=options)
    assert "Binary & hex: Denary to binary" in text
    assert "Pearson Edexcel 1CP2 2.1.3 · seed 42 · medium · 10 questions" in text
    assert "Aim: Convert a denary number" in text and "[Worked example]" in text
    sheet = text.split("ANSWER KEY")[0]
    assert sheet.index("Warm-up") < sheet.index("Practice") < sheet.index("Stretch")
    assert " 10. Convert" in sheet  # numbered straight through the sections
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == [
        "binary_denary_to_binary_medium_s42.pdf",
        "binary_denary_to_binary_medium_s42_key.pdf",
    ]


def test_header_says_where_an_off_board_lesson_belongs(tmp_path: Path) -> None:
    assert "Not on OCR J277 · on Pearson Edexcel 1CP2 2.1.3" in _run(
        tmp_path, "twos-complement/to-twos-complement"
    )
    assert "Beyond GCSE (A level)" in _run(tmp_path, "logic/simplification")
    assert "AQA 8525 3.3.8" in _run(tmp_path, "compression/huffman", board="aqa")


def test_header_states_the_gate_set_for_the_board_and_level(tmp_path: Path) -> None:
    def preview(board: str, difficulty: str = "medium", level: str = "gcse") -> str:
        options = Options(count=3, seed=11, formats="docx", difficulty=difficulty)  # type: ignore[arg-type]
        return _run(tmp_path, "logic/review-truth-tables", board, options=options, level=level)

    assert "gates: AND, OR, NOT" in preview("ocr")
    assert "gates: AND, OR, NOT, XOR" in preview("aqa")
    edexcel = preview("edexcel", difficulty="hard")
    assert "gates: AND, OR, NOT" in edexcel and "XOR" not in edexcel
    assert "NAND" not in preview("aqa", difficulty="hard")
    hard_a_level = preview("ocr", difficulty="hard", level="a_level")
    assert "A-level" in hard_a_level and "gates: AND, OR, NOT, XOR, NAND, NOR" in hard_a_level
    lesson = _run(tmp_path, "logic/two-gates", "aqa")
    assert "AQA 8525 3.4.2" in lesson and "gates: AND, OR, NOT, XOR" in lesson


def test_header_states_the_laws_practised(tmp_path: Path) -> None:
    text = _run(tmp_path, "logic/review-simplification")
    assert "laws: absorption, distributive, complement" in text and "identity" not in text
    text = _run(tmp_path, "logic/simplification", laws="identities")
    assert "laws: identity, idempotent, double negation, complement" in text


def test_cli_make_and_lessons(tmp_path: Path) -> None:
    out = ["-f", "pdf", "--out", str(tmp_path)]
    r = runner.invoke(app, ["worksheet", "make", "--topic", "binary", "-n", "4", *out])
    assert r.exit_code == 0, r.output
    assert "Worksheet: Binary, denary and hexadecimal" in r.output and "seed 42" in r.output
    assert (tmp_path / "binary_medium_s42.pdf").exists()
    assert (tmp_path / "binary_medium_s42_key.pdf").exists()
    r = runner.invoke(app, ["worksheet", "make", "binary", "-n", "4", *out])  # unit: its Review
    assert r.exit_code == 0 and "Worksheet: Binary, denary and hexadecimal" in r.output
    r = runner.invoke(
        app, ["worksheet", "make", "binary", "--lesson", "denary-to-binary", "-n", "4", *out]
    )
    assert r.exit_code == 0, r.output
    assert "Binary & hex: Denary to binary" in r.output and "Warm-up" in r.output
    assert (tmp_path / "binary_denary_to_binary_medium_s42.pdf").exists()
    r = runner.invoke(app, ["worksheet", "make", "--topic", "shifts", "-n", "2", *out])
    assert r.exit_code == 0 and "Worksheet: Logical and arithmetic shifts" in r.output
    r = runner.invoke(app, ["worksheet", "lessons"])
    assert r.exit_code == 0 and "denary-to-binary" in r.output and "huffman" in r.output
    r = runner.invoke(app, ["worksheet", "topics"])
    assert r.exit_code == 0 and "huffman" in r.output
    r = runner.invoke(app, ["worksheet", "make", "--help"], terminal_width=200)
    plain = " ".join(re.sub(r"\x1b\[[0-9;]*m", "", r.output).replace("│", " ").split())
    assert "staff worksheet make binary --lesson denary-to-binary" in plain  # CI colours help
    for bad in (["--topic", "nope"], ["binary", "--lesson", "nope"], ["binary", "-t", "rle"]):
        r = runner.invoke(app, ["worksheet", "make", *bad, *out])
        assert r.exit_code == 1, bad


def test_cli_level_and_board_options(tmp_path: Path) -> None:
    args = ["worksheet", "make", "-t", "truth_tables", "-n", "2", "-f", "pdf", "-o", str(tmp_path)]
    r = runner.invoke(app, [*args, "--board", "aqa", "--level", "a_level", "--difficulty", "hard"])
    assert r.exit_code == 0, r.output
    assert "A-level" in r.output and "NAND, NOR" in r.output
    assert (tmp_path / "truth_tables_hard_alevel_s42.pdf").exists()  # a GCSE file keeps its name
    r = runner.invoke(app, [*args, "--board", "edexcel"])
    assert r.exit_code == 0 and "gates: AND, OR, NOT" in r.output and "XOR" not in r.output
    r = runner.invoke(app, [*args, "--board", "wjec"])
    assert r.exit_code == 1 and "ocr|aqa|edexcel" in r.output
    r = runner.invoke(app, [*args, "--level", "degree"])
    assert r.exit_code == 1
    r = runner.invoke(app, [*args, "--laws", "nope"])
    assert r.exit_code == 1


def test_count_outside_the_range_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    out = tmp_path / "out"
    for lesson in (["-t", "binary"], ["binary", "--lesson", "denary-to-binary"]):
        args = ["worksheet", "make", *lesson, "-f", "pdf", "-o", str(out)]
        for count in ("0", "500"):
            r = runner.invoke(app, [*args, "--count", count])
            assert r.exit_code == 1, r.output
            assert f"Questions must be between 1 and 60 (you asked for {count})." in r.output
    assert not out.exists() or list(out.iterdir()) == []  # no empty sheet, no empty key
    ctx = RunContext(config=load_config(), output_dir=out)
    with pytest.raises(ToolError, match="you asked for 0"):
        plugin.run({"lesson": "binary/review", "options": Options(count=0, formats="docx")}, ctx)
