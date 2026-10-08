"""Worksheet: seeded random theory questions with keys, in the house style."""

from __future__ import annotations

from typing import Any

from staffroom.core.export import export, house_style_from, to_text
from staffroom.core.panel import PanelSpec
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.tools.worksheet import logic
from staffroom.tools.worksheet.panel import panel_spec
from staffroom.tools.worksheet.sheet import build_document


def formats_for(choice: str) -> tuple[str, ...]:
    return ("docx", "pdf") if choice == "both" else (choice,)


class WorksheetPlugin:
    name = "worksheet"
    description = "Seeded theory question sets (binary, logic, sizes, compression) with keys."
    version = "0.1.0"

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.worksheet.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options", logic.Options())
        board = ctx.config.general.board  # gates follow the teacher's board unless A-level
        ctx.progress(0.2, "Generating questions")
        try:
            questions = logic.generate(
                options.topic,
                options.seed,
                options.count,
                options.difficulty,
                board=board,
                level=options.level,
                laws=options.laws,
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        doc = build_document(questions, options, board=board)
        ctx.progress(0.6, "Writing files")
        level = "_alevel" if options.level == "a_level" else ""  # so GCSE files are not overwritten
        stem = f"{options.topic}_{options.difficulty}{level}_s{options.seed}"
        files = export(
            doc,
            ctx.output_dir,
            stem,
            formats_for(options.formats),
            style=house_style_from(ctx.config),
        )
        note = logic.header_note(options, board)
        ctx.log(
            f"{len(questions)} questions, seed {options.seed}, {options.difficulty}"
            + (f", {note}" if note else "")
        )
        ctx.progress(1.0, "Done")
        preview = to_text(doc.sheet()) + "\n\n" + to_text(doc.key())
        return RunResult(
            texts={"preview": preview},
            files=files,
            summary=f"Wrote {', '.join(f.name for f in files)} to {ctx.output_dir}",
        )


plugin = WorksheetPlugin()
