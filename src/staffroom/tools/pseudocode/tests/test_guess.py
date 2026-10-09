"""Guessing the source language from the code itself (#27)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from staffroom.cli import app
from staffroom.core.config import load_config
from staffroom.core.plugin import RunContext, ToolError
from staffroom.tools.pseudocode import logic, plugin
from staffroom.tools.pseudocode.logic import Options

runner = CliRunner()

PYTHON = 'x = int(input("n: "))\nif x > 3:\n    print("big")\n'
OCR = 'x = int(input("n: "))\nif x > 3 then\n    print("big")\nendif\n'
AQA = 'x ← STRING_TO_INT(USERINPUT)\nIF x > 3 THEN\n    OUTPUT "big"\nENDIF\n'


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (PYTHON, "python"),
        (OCR, "ocr"),
        (AQA, "aqa"),
        ("def area(w, h):\n    return w * h\n", "python"),
        ("for i = 0 to 4\n    print(i)\nnext i\n", "ocr"),
        ("procedure shout(msg)\n    print(msg)\nendprocedure\n", "ocr"),
        ("SUBROUTINE shout(msg)\n    OUTPUT msg\nENDSUBROUTINE\n", "aqa"),
        ("WHILE x < 3\n    x ← x + 1\nENDWHILE\n", "aqa"),
    ],
)
def test_guess_dialect(text: str, expected: str) -> None:
    assert logic.guess_dialect(text) == expected


def test_guess_is_none_when_nothing_distinguishes() -> None:
    assert logic.guess_dialect("x = 5\nprint(x)\n") is None
    assert logic.guess_dialect("") is None


def test_guess_ignores_strings_and_comments() -> None:
    # Words inside strings or comments are not evidence of a language.
    assert logic.guess_dialect('print("endif then next")\n') is None
    assert logic.guess_dialect("// OUTPUT the total with endwhile\nx = 5\n") is None
    assert logic.guess_dialect('# def endif\nif x then\n    print("USERINPUT")\nendif\n') == "ocr"


def test_dialect_from_name() -> None:
    assert logic.dialect_from_name("prog.py") == "python"
    assert logic.dialect_from_name("prog.aqa.txt") == "aqa"
    assert logic.dialect_from_name("prog.ocr.txt") == "ocr"
    assert logic.dialect_from_name("notes.txt") is None


def _ctx(tmp_path: Path) -> RunContext:
    return RunContext(config=load_config(), output_dir=tmp_path)


def test_plugin_guesses_and_says_so(tmp_path: Path) -> None:
    logged: list[str] = []
    ctx = RunContext(config=load_config(), output_dir=tmp_path, log=logged.append)
    result = plugin.run({"pasted": AQA, "options": Options(target="ocr")}, ctx)
    assert "if x > 3 then" in result.texts["output"]
    assert "input guessed as AQA pseudocode" in result.summary
    assert any("Treated input as AQA pseudocode" in m and "--from" in m for m in logged)


def test_plugin_explicit_source_is_not_called_a_guess(tmp_path: Path) -> None:
    opts = Options(source="aqa", target="ocr")
    result = plugin.run({"pasted": AQA, "options": opts}, _ctx(tmp_path))
    assert "guessed" not in result.summary


def test_plugin_falls_back_to_the_file_name(tmp_path: Path) -> None:
    src = tmp_path / "simple.aqa.txt"
    src.write_text("x = 5\nprint(x)\n")
    result = plugin.run({"source": src, "options": Options(target="python")}, _ctx(tmp_path))
    assert "input guessed as AQA pseudocode" in result.summary


def test_plugin_refuses_when_guess_is_the_target(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="already looks like OCR Exam Reference Language"):
        plugin.run({"pasted": OCR, "options": Options(target="ocr")}, _ctx(tmp_path))
    with pytest.raises(ToolError, match="--from python or --from aqa"):
        plugin.run({"pasted": OCR, "options": Options(target="ocr")}, _ctx(tmp_path))


def test_plugin_refuses_when_ambiguous(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="Could not tell") as info:
        inputs = {"pasted": "x = 5\nprint(x)\n", "options": Options(target="aqa")}
        plugin.run(inputs, _ctx(tmp_path))
    assert "--from python or --from ocr" in str(info.value)


def test_plugin_refuses_same_explicit_source_and_target(tmp_path: Path) -> None:
    with pytest.raises(ToolError, match="both Python"):
        plugin.run(
            {"pasted": PYTHON, "options": Options(source="python", target="python")},
            _ctx(tmp_path),
        )


def test_cli_to_ocr_from_txt_guesses_aqa(tmp_path: Path) -> None:
    # The audit case: `to-ocr notes.txt` used to assume OCR and refuse.
    notes = tmp_path / "notes.txt"
    notes.write_text(AQA)
    r = runner.invoke(app, ["pseudocode", "to-ocr", str(notes)])
    assert r.exit_code == 0, r.output
    assert "if x > 3 then" in r.output and "Treated input as AQA pseudocode" in r.output


def test_cli_says_what_to_pass_when_the_source_is_the_target(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet.txt"
    sheet.write_text(OCR)
    r = runner.invoke(app, ["pseudocode", "to-ocr", str(sheet)])
    assert r.exit_code == 1
    assert "already looks like OCR Exam Reference Language" in r.output
    assert "--from python or --from aqa" in r.output


def test_cli_explicit_from_still_wins(tmp_path: Path) -> None:
    sheet = tmp_path / "sheet.txt"
    sheet.write_text(OCR)
    r = runner.invoke(app, ["pseudocode", "to-aqa", str(sheet), "--from", "ocr"])
    assert r.exit_code == 0 and "guessed" not in r.output
    r = runner.invoke(app, ["pseudocode", "to-ocr", str(sheet), "--from", "ocr"])
    assert r.exit_code == 1 and "cannot translate from 'ocr' to 'ocr'" in r.output
