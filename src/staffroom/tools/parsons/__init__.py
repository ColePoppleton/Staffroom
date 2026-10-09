"""Parsons: working code → a shuffle-the-blocks worksheet with a key."""

from __future__ import annotations

from typing import Any

from staffroom.core.codeinput import code_from_inputs
from staffroom.core.export import export, house_style_from, to_text
from staffroom.core.panel import PanelSpec
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.tools.parsons import logic
from staffroom.tools.parsons.panel import panel_spec
from staffroom.tools.parsons.sheet import build_document


def formats_for(choice: str) -> tuple[str, ...]:
    return ("docx", "pdf") if choice == "both" else (choice,)


class ParsonsPlugin:
    name = "parsons"
    description = "Working code → Parsons problem worksheet + answer key."
    version = "0.1.0"
    group, glyph = "From a program", "blocks"  # sidebar group and glyph (#89)

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.parsons.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options", logic.Options())
        source, name = code_from_inputs(inputs)

        ctx.progress(0.2, "Splitting into blocks")
        try:
            problem = logic.make_problem(source, options)
        except SyntaxError as exc:
            raise ToolError(f"That is not valid Python: {exc.msg} (line {exc.lineno})") from exc
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        ctx.log(
            f"{len(problem.solution)} blocks, {len(problem.distractor_numbers())} distractors, "
            f"seed {problem.seed}"
        )
        doc = build_document(problem, name, options)
        ctx.progress(0.6, "Writing files")
        stem = f"{name}_parsons_s{problem.seed}"
        files = export(
            doc,
            ctx.output_dir,
            stem,
            formats_for(options.formats),
            style=house_style_from(ctx.config),
        )
        ctx.progress(1.0, "Done")
        preview = to_text(doc.sheet()) + "\n\n" + to_text(doc.key())
        return RunResult(
            texts={"preview": preview},
            files=files,
            summary=f"Wrote {', '.join(f.name for f in files)} to {ctx.output_dir}",
            outcome=(
                f"{len(problem.solution)} blocks · "
                f"{len(problem.distractor_numbers())} distractors, seed {problem.seed}"
            ),
        )


plugin = ParsonsPlugin()
