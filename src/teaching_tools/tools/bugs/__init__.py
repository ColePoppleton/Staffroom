"""Bugs: inject controlled errors into working code; the key says what each does."""

from __future__ import annotations

from typing import Any

from teaching_tools.core.codeinput import code_from_inputs
from teaching_tools.core.export import export, house_style_from, to_text
from teaching_tools.core.panel import PanelSpec
from teaching_tools.core.plugin import Inputs, RunContext, RunResult, ToolError
from teaching_tools.core.runner import RunOutcome, run_source
from teaching_tools.core.table import Table
from teaching_tools.tools.bugs import logic
from teaching_tools.tools.bugs.panel import panel_spec
from teaching_tools.tools.bugs.sheet import build_document

TIMEOUT = 4.0


def formats_for(choice: str) -> tuple[str, ...]:
    return ("docx", "pdf") if choice == "both" else (choice,)


def classify(original: RunOutcome, variant: RunOutcome) -> str:
    """What the key says about a variant, from two sandbox runs."""
    if variant.blocked_imports:
        return "refused: imports " + ", ".join(variant.blocked_imports)
    if variant.timed_out:
        return "hangs (infinite loop)"
    if variant.crashed:
        return f"crashes: {variant.exception_name or 'error'}"
    if variant.stdout != original.stdout:
        return "runs, but the output is wrong"
    return "no visible change (still runs the same)"


class BugsPlugin:
    name = "bugs"
    description = "Inject one controlled error per copy; key says crash / wrong output / silent."
    version = "0.1.0"

    def register_cli(self, app: Any) -> None:
        from teaching_tools.tools.bugs.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options", logic.Options())
        try:
            source, name = code_from_inputs(inputs)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        stdin = str(inputs.get("stdin") or "")
        if stdin and not stdin.endswith("\n"):
            stdin += "\n"
        if not options.kinds():
            raise ToolError("Tick at least one error class.")
        ctx.progress(0.1, "Finding places to break")
        try:
            variants = logic.make_variants(source, options)
        except SyntaxError as exc:
            raise ToolError(f"That is not valid Python: {exc.msg} (line {exc.lineno})") from exc
        if not variants:
            raise ToolError("No suitable lines for the chosen error classes.")
        if len(variants) < options.count:
            ctx.log(f"Only {len(variants)} distinct mutations possible; asked for {options.count}.")

        ctx.progress(0.3, "Running the original")
        baseline = run_source(source, stdin=stdin, timeout=TIMEOUT)
        if baseline.blocked_imports:
            raise ToolError("Refusing to run: imports " + ", ".join(baseline.blocked_imports))
        if not baseline.ok:
            ctx.log(
                f"Note: the original program {baseline.describe()}; outcomes compare against that."
            )
        for i, v in enumerate(variants, 1):
            ctx.progress(0.3 + 0.5 * i / len(variants), f"Running variant {i}")
            v.outcome = classify(baseline, run_source(v.source, stdin=stdin, timeout=TIMEOUT))
            ctx.log(f"Variant {i}: line {v.mutation.line}, {v.mutation.label} → {v.outcome}")

        ctx.progress(0.85, "Writing files")
        out = ctx.output_dir
        out.mkdir(parents=True, exist_ok=True)
        files = []
        for v in variants:
            path = out / f"{name}_bug{v.number}.py"
            path.write_text(v.source, encoding="utf-8")
            files.append(path)
        doc = build_document(name, source, variants)
        files += export(
            doc,
            out,
            f"{name}_bugs",
            formats_for(options.formats),
            style=house_style_from(ctx.config),
        )
        ctx.progress(1.0, "Done")
        key = Table(
            ["Version", "Line", "Bug", "Original", "Changed to", "What happens"],
            [
                [
                    v.number,
                    v.mutation.line,
                    v.mutation.label,
                    v.mutation.original.strip(),
                    v.mutation.mutated.strip(),
                    v.outcome,
                ]
                for v in variants
            ],
        )
        return RunResult(
            tables={"key": key},
            texts={"preview": to_text(doc.sheet()) + "\n\n" + to_text(doc.key())},
            files=files,
            summary=f"{len(variants)} variants written to {out}",
        )


plugin = BugsPlugin()
