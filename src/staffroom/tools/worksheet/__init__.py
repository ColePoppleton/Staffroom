"""Worksheet: seeded random theory questions with keys, in the house style."""

from __future__ import annotations

from typing import Any

from staffroom.core import spec
from staffroom.core.export import export, house_style_from, to_text
from staffroom.core.panel import PanelSpec, pages_from
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.tools.worksheet import lessons, logic
from staffroom.tools.worksheet.panel import panel_spec
from staffroom.tools.worksheet.sheet import lesson_title, make_document


def formats_for(choice: str) -> tuple[str, ...]:
    return ("docx", "pdf") if choice == "both" else (choice,)


class WorksheetPlugin:
    name = "worksheet"
    description = "Lesson sheets on binary, logic, file sizes and compression, with keys."
    version = "0.1.0"
    group, glyph = "Sheets & quizzes", "page"  # sidebar group and glyph (#89)

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.worksheet.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options") or logic.Options()
        try:
            lesson = lessons.resolve(str(inputs.get("lesson") or lessons.DEFAULT_LESSON))
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        settings = lessons.Settings(
            board=ctx.config.general.board,  # gates and units follow the teacher's board
            level=inputs.get("level") or "gcse",
            laws=inputs.get("laws") or "absorption",
        )
        ctx.progress(0.2, "Generating questions")
        try:
            made = make_document(
                lesson, options.seed, options.count, options.difficulty, settings, spec.BOARDS
            )
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        doc, questions, note = made.doc, made.questions, made.note
        ctx.progress(0.6, "Writing files")
        files = export(
            doc,
            ctx.output_dir,
            made.stem,
            formats_for(options.formats),
            style=house_style_from(ctx.config),
        )
        ctx.log(
            f"{lesson_title(lesson)}: {len(questions)} questions, seed {options.seed}, "
            f"{options.difficulty}" + (f", {note}" if note else "")
        )
        ctx.progress(1.0, "Done")
        sheet_text, key_text = to_text(doc.sheet()), to_text(doc.key())
        return RunResult(
            texts={"preview": sheet_text + "\n\n" + key_text},  # the CLI's --preview
            pages={"pages": pages_from(files, sheet_text=sheet_text, key_text=key_text)},
            files=files,
            summary=f"Wrote {', '.join(f.name for f in files)} to {ctx.output_dir}",
            outcome=(
                f"{lesson.title} · {len(questions)} questions · "
                f"seed {options.seed}, {options.difficulty}"
            ),
        )


plugin = WorksheetPlugin()
