from pathlib import Path

from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext
from staffroom.tools.pseudocode import plugin
from staffroom.tools.pseudocode.logic import Options

runner = CliRunner()
CODE = 'x = int(input("n: "))\nif x > 3:\n    print("big")\n'


def test_plugin_writes_translation(tmp_path: Path) -> None:
    ctx = RunContext(config=load_config(), output_dir=tmp_path)
    result = plugin.run({"pasted": CODE, "options": Options(direction="python_to_aqa")}, ctx)
    assert "OUTPUT" in result.texts["output"] and "Everything translated" in result.texts["report"]
    assert (tmp_path / "pasted_code.aqa.txt").read_text() == result.texts["output"]


def test_cli_to_ocr_and_back(tmp_path: Path) -> None:
    src = tmp_path / "prog.py"
    src.write_text(CODE)
    r = runner.invoke(app, ["pseudocode", "to-ocr", str(src), "--save", "--out", str(tmp_path)])
    assert r.exit_code == 0, r.output
    assert 'x = int(input("n: "))' in r.output and "if x > 3 then" in r.output
    erl = tmp_path / "prog.ocr.txt"
    assert erl.exists()
    r = runner.invoke(app, ["pseudocode", "to-python", str(erl)])
    assert r.exit_code == 0, r.output
    assert "if x > 3:" in r.output
    r = runner.invoke(app, ["pseudocode", "to-aqa", str(erl), "--from", "ocr"])
    assert r.exit_code == 0 and "x ← STRING_TO_INT(USERINPUT)" in r.output
    r = runner.invoke(app, ["pseudocode", "to-python", str(src)])
    assert r.exit_code == 1
