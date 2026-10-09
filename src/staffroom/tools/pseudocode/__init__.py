"""Pseudocode: Python ↔ OCR ERL ↔ AQA, with an explicit could-not-translate list."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from staffroom.core.codeinput import code_from_inputs
from staffroom.core.panel import PanelSpec
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.tools.pseudocode import logic
from staffroom.tools.pseudocode.panel import panel_spec


class PseudocodePlugin:
    name = "pseudocode"
    description = "Python ↔ OCR ERL / AQA pseudocode (GCSE subset) with a could-not-translate list."
    version = "0.1.0"

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.pseudocode.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options", logic.Options())
        text, name = code_from_inputs(inputs)
        picked = inputs.get("source")
        filename = picked.name if isinstance(picked, Path) else ""
        dst = options.target
        src, guessed = _resolve_source(options.source, text, filename, dst)
        if guessed:
            ctx.log(
                f"Treated input as {logic.LANGUAGE_LABELS[src]} (guessed from the code); "
                "pass --from, or set From in the panel, to override."
            )
        ctx.progress(0.3, f"{logic.LANGUAGE_LABELS[src]} → {logic.LANGUAGE_LABELS[dst]}")
        try:
            result = logic.translate(text, src, dst)
        except SyntaxError as exc:
            raise ToolError(f"That is not valid Python: {exc.msg} (line {exc.lineno})") from exc
        for d in result.dropped:
            ctx.log("Could not translate " + d)
        for n in result.notes:
            ctx.log("Note: " + n)
        files = []
        if options.formats == "txt":
            out = ctx.output_dir / f"{name}{logic.extension_for(dst)}"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(result.text, encoding="utf-8")
            files.append(out)
        ctx.progress(1.0, "Done")
        status = (
            "everything translated"
            if result.clean
            else f"{len(result.dropped)} line(s) could not be translated"
        )
        summary = f"{logic.LANGUAGE_LABELS[dst]}: {status}"
        if guessed:
            summary += f"; input guessed as {logic.LANGUAGE_LABELS[src]}"
        if files:
            summary += f"; wrote {files[0].name}"
        return RunResult(
            texts={"output": result.text, "report": result.report()}, files=files, summary=summary
        )


def _resolve_source(
    source: logic.Source, text: str, filename: str, target: logic.Language
) -> tuple[logic.Language, bool]:
    """The language to read the input as, and whether it was guessed.

    An explicit source is taken as given. ``guess`` looks at the code first
    and the file name second; what cannot be told apart, or turns out to be
    the target language already, is a :class:`ToolError` that names the
    option to pass instead of a silent wrong translation."""
    others = " or ".join(f"--from {lang}" for lang in logic.LANGUAGES if lang != target)
    if source != "guess":
        if source == target:
            raise ToolError(
                f"From and To are both {logic.LANGUAGE_LABELS[target]}; choose a different To, "
                f"or {others} on the command line."
            )
        return source, False
    guess = logic.guess_dialect(text) or logic.dialect_from_name(filename)
    if guess is None:
        raise ToolError(
            "Could not tell whether the input is Python, OCR ERL or AQA pseudocode: "
            f"say which with {others} on the command line, or From in the panel."
        )
    if guess == target:
        raise ToolError(
            f"The input already looks like {logic.LANGUAGE_LABELS[target]}, the language asked "
            f"for. Choose a different To, or say what the input is with {others} on the "
            "command line."
        )
    return guess, True


plugin = PseudocodePlugin()
