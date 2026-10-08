from pathlib import Path

from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import Config, GeneralSettings, load_config
from staffroom.core.plugin import RunContext
from staffroom.tools.worksheet import plugin
from staffroom.tools.worksheet.logic import Options

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
    assert "gates: AND, OR, NOT" in preview  # the default board is OCR


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


def test_header_states_the_gate_set_for_the_board_and_level(tmp_path: Path) -> None:
    def preview(board: str, **opts: object) -> str:
        cfg = Config(general=GeneralSettings(board=board), path=tmp_path / "config.toml")
        ctx = RunContext(config=cfg, output_dir=tmp_path)
        options = Options(topic="truth_tables", count=3, seed=11, formats="docx", **opts)  # type: ignore[arg-type]
        return plugin.run({"options": options}, ctx).texts["preview"]

    assert "gates: AND, OR, NOT" in preview("ocr")
    assert "gates: AND, OR, NOT, XOR" in preview("aqa")
    assert "NAND" not in preview("aqa", difficulty="hard")
    hard_a_level = preview("ocr", difficulty="hard", level="a_level")
    assert "A-level" in hard_a_level and "gates: AND, OR, NOT, XOR, NAND, NOR" in hard_a_level


def test_header_states_the_laws_practised(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    options = Options(topic="boolean_simplification", count=3, seed=11, formats="docx")
    text = plugin.run({"options": options}, ctx).texts["preview"]
    assert "laws: absorption, distributive, complement" in text and "identity" not in text
    options = Options(
        topic="boolean_simplification", count=3, seed=11, formats="docx", laws="identities"
    )
    text = plugin.run({"options": options}, ctx).texts["preview"]
    assert "laws: identity, idempotent, double negation, complement" in text


def test_cli_level_and_board_options(tmp_path: Path) -> None:
    args = ["worksheet", "make", "-t", "truth_tables", "-n", "2", "-f", "pdf", "-o", str(tmp_path)]
    r = runner.invoke(app, [*args, "--board", "aqa", "--level", "a_level", "--difficulty", "hard"])
    assert r.exit_code == 0, r.output
    assert "A-level" in r.output and "NAND, NOR" in r.output
    assert (tmp_path / "truth_tables_hard_alevel_s42.pdf").exists()  # a GCSE file keeps its name
    r = runner.invoke(app, [*args, "--level", "degree"])
    assert r.exit_code == 1
    r = runner.invoke(app, [*args, "--laws", "nope"])
    assert r.exit_code == 1
