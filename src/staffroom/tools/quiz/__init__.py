"""Quiz: author once in Markdown, export to Kahoot / Forms / printable do-now."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from staffroom.core.export import house_style_from, to_text
from staffroom.core.panel import PanelSpec
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.tools.quiz import logic
from staffroom.tools.quiz.export import donow_document, write_donow, write_forms, write_kahoot
from staffroom.tools.quiz.panel import panel_spec


def load_bank(path: Path) -> logic.Bank:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"Could not read {path}: {exc}") from exc
    bank = logic.parse_bank(text)
    if not bank.questions:
        raise ToolError(
            "No questions found. Each question starts with '## ' (see examples/question_bank.md)."
        )
    return bank


def _as_of(text: str) -> date:
    """The retrieval date from the option, today when blank."""
    if not text.strip():
        return date.today()
    try:
        return date.fromisoformat(text.strip())
    except ValueError:
        raise ToolError(
            f"The 'as of' date should look like 2026-10-08 (YYYY-MM-DD), not {text!r}."
        ) from None


class QuizPlugin:
    name = "quiz"
    description = (
        "Markdown question bank → Kahoot, Forms text, printable do-now; retrieval scheduler."
    )
    version = "0.1.0"

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.quiz.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options", logic.Options())
        source: Path | None = inputs.get("source")
        if source is None:
            raise ToolError("Choose a question bank first.")
        bank = load_bank(source)
        for err in bank.errors:
            ctx.log("Bank: " + err)
        pool = logic.filter_questions(bank.questions, options.topics, options.spec)
        ctx.log(f"{len(bank.questions)} questions in the bank, {len(pool)} after filters")

        if options.retrieval:
            log_path: Path | None = inputs.get("taught_log")
            if log_path is None:
                raise ToolError("Retrieval mode needs a taught log (date,topic CSV).")
            try:
                entries, errors = logic.parse_taught_log(log_path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                raise ToolError(
                    f"Could not find {log_path.name} (looked in {log_path.parent})."
                ) from None
            except OSError as exc:
                reason = exc.strerror or exc.__class__.__name__
                raise ToolError(f"Could not read {log_path.name}: {reason}.") from exc
            except UnicodeDecodeError as exc:
                raise ToolError(
                    f"Could not read {log_path.name} as text: the taught log is a plain CSV "
                    "with date,topic columns."
                ) from exc
            for err in errors:
                ctx.log("Log: " + err)
            today = _as_of(options.today)
            chosen, windows = logic.retrieval_pick(
                pool, entries, today, options.count, options.seed
            )
            for w, topics in windows.items():
                ctx.log(f"{w} week(s) ago: {', '.join(topics) or 'nothing taught'}")
            if not chosen:
                raise ToolError("No questions match the topics taught 1, 3 and 6 weeks ago.")
        else:
            chosen = logic.choose(pool, options.count, options.seed)
            if not chosen:
                raise ToolError("No questions match those filters.")

        notes: list[str] = []
        stem = source.stem
        written = chosen
        count_phrase = f"{len(chosen)} questions"
        ctx.progress(0.6, "Writing")
        if options.fmt == "kahoot":
            # Distractors come from the whole bank, not only the chosen questions,
            # so a short answer is rarely skipped and stays within its topic.
            sheet = logic.kahoot_sheet(chosen, bank.questions)
            notes = sheet.notes
            if not sheet.rows:
                for n in notes:
                    ctx.log("Note: " + n)
                raise ToolError(
                    "Nothing could be exported for Kahoot: "
                    + "; ".join(f"Q{q.number} {reason}" for q, reason in sheet.skipped)
                    + ". Add more short-answer questions to the bank, or export as forms "
                    "or donow."
                )
            written = list(sheet.written)
            count_phrase = logic.kahoot_report(sheet, len(chosen))
            files = write_kahoot(sheet.rows, ctx.output_dir, stem)
            preview = (ctx.output_dir / f"{stem}_kahoot.csv").read_text(encoding="utf-8")
        elif options.fmt == "forms":
            files = write_forms(chosen, ctx.output_dir, stem, options.title)
            preview = files[0].read_text(encoding="utf-8")
        else:
            files = write_donow(
                chosen, ctx.output_dir, stem, options.title, house_style_from(ctx.config)
            )
            doc = donow_document(chosen, options.title)
            preview = to_text(doc.sheet()) + "\n\n" + to_text(doc.key())
        for n in notes:
            ctx.log("Note: " + n)
        ctx.progress(1.0, "Done")
        return RunResult(
            tables={"chosen": logic.selection_table(written)},
            texts={"preview": preview},
            files=files,
            summary=f"{count_phrase} → {', '.join(f.name for f in files)} in {ctx.output_dir}",
        )


plugin = QuizPlugin()
