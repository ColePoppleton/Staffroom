"""Pseudocode: Python ↔ OCR ERL ↔ AQA, with an explicit could-not-translate list."""

from __future__ import annotations

from typing import Any

from teaching_tools.core.codeinput import code_from_inputs
from teaching_tools.core.panel import PanelSpec
from teaching_tools.core.plugin import Inputs, RunContext, RunResult, ToolError
from teaching_tools.tools.pseudocode import logic
from teaching_tools.tools.pseudocode.panel import panel_spec


class PseudocodePlugin:
    name = "pseudocode"
    description = "Python ↔ OCR ERL / AQA pseudocode (GCSE subset) with a could-not-translate list."
    version = "0.1.0"

    def register_cli(self, app: Any) -> None:
        from teaching_tools.tools.pseudocode.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options", logic.Options())
        try:
            text, name = code_from_inputs(inputs)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        src, dst = logic.split_direction(options.direction)
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
        return RunResult(
            texts={"output": result.text, "report": result.report()},
            files=files,
            summary=f"{logic.LANGUAGE_LABELS[dst]}: {status}"
            + (f"; wrote {files[0].name}" if files else ""),
        )


plugin = PseudocodePlugin()
