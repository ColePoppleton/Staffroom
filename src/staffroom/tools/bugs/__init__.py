"""Bugs: inject controlled errors into working code; the key says what each does."""

from __future__ import annotations

from typing import Any

from staffroom.core.codeinput import code_from_inputs
from staffroom.core.export import export, house_style_from, to_text
from staffroom.core.panel import PanelSpec, pages_from
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.core.runner import RunOutcome, capped_note, run_source
from staffroom.core.table import Table
from staffroom.tools.bugs import logic
from staffroom.tools.bugs.panel import panel_spec
from staffroom.tools.bugs.sheet import build_document

TIMEOUT = logic.TIMEOUT


def formats_for(choice: str) -> tuple[str, ...]:
    return ("docx", "pdf") if choice == "both" else (choice,)


SILENT = "silent: no visible change (still runs the same)"


def runs_the_same(original: RunOutcome, variant: RunOutcome) -> bool:
    """Would running the variant look exactly like running the original?
    Same output and the same ending (finished, crashed with the same error,
    or hung). Such a bug can only be found by reading the code."""
    return (
        not variant.blocked_imports
        and variant.stdout == original.stdout
        and variant.timed_out == original.timed_out
        and variant.crashed == original.crashed
        and variant.exception_name == original.exception_name
    )


# Errors Python reports before the program starts: one per sheet is plenty.
COMPILE_ERRORS = frozenset({"SyntaxError", "IndentationError", "TabError"})


def outcome_kind(original: RunOutcome, variant: RunOutcome) -> logic.Outcome:
    """The outcome class ``logic.choose`` balances, from two sandbox runs."""
    if runs_the_same(original, variant) and not variant.blocked_imports:
        return "silent"
    if variant.timed_out:
        return "hang"
    if variant.crashed and variant.exception_name in COMPILE_ERRORS:
        return "syntax_error"
    if variant.crashed or variant.blocked_imports:
        return "crash"
    return "wrong_output"


def classify(original: RunOutcome, variant: RunOutcome) -> str:
    """What the key says about a variant, from two sandbox runs."""
    if variant.blocked_imports:
        return "refused: imports " + ", ".join(variant.blocked_imports)
    if runs_the_same(original, variant):
        text = SILENT
    elif variant.timed_out:
        text = "hangs (infinite loop)"
    elif variant.crashed:
        text = f"crashes: {variant.exception_name or 'error'}"
    else:
        text = "runs, but the output is wrong"
    if variant.truncated:
        text += f"; {capped_note(variant.output_limit)}"
    return text


class BugsPlugin:
    name = "bugs"
    description = "Inject one controlled error per copy; key says crash / wrong output / silent."
    version = "0.1.0"
    group, glyph = "From a program", "bug"  # sidebar group and glyph (#89)

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.bugs.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options", logic.Options())
        source, name = code_from_inputs(inputs)
        stdin = str(inputs.get("stdin") or "")
        if stdin and not stdin.endswith("\n"):
            stdin += "\n"
        if not options.kinds():
            raise ToolError("Tick at least one error class.")
        ctx.progress(0.1, "Running the original")
        baseline = run_source(source, stdin=stdin, timeout=TIMEOUT)
        if baseline.blocked_imports:
            raise ToolError("Refusing to run: imports " + ", ".join(baseline.blocked_imports))
        if not baseline.ok:
            ctx.log(
                f"Note: the original program {baseline.describe()}; outcomes compare against that."
            )

        # Every candidate the selection looks at runs once, in the sandbox; the
        # selection itself is logic.choose, in the seed's order.
        runs: dict[logic.Mutation, RunOutcome] = {}

        def outcome_of(m: logic.Mutation) -> logic.Outcome:
            ctx.progress(min(0.8, 0.2 + 0.04 * len(runs)), f"Trying a bug on line {m.line}")
            runs[m] = run_source(logic.apply(source, m), stdin=stdin, timeout=TIMEOUT)
            return outcome_kind(baseline, runs[m])

        ctx.progress(0.2, "Finding places to break")
        try:
            variants = logic.make_variants(source, options, outcome_of)
        except SyntaxError as exc:
            raise ToolError(f"That is not valid Python: {exc.msg} (line {exc.lineno})") from exc
        kept = {v.mutation for v in variants}
        dropped = [m for m, r in runs.items() if m not in kept and runs_the_same(baseline, r)]
        for m in dropped:
            ctx.log(f"Skipped line {m.line}, {m.label}: runs the same as the original")
        outcomes = [outcome_kind(baseline, runs[v.mutation]) for v in variants]
        syntax = outcomes.count("syntax_error")
        if syntax == 1:
            for m, r in runs.items():
                if m not in kept and outcome_kind(baseline, r) == "syntax_error":
                    ctx.log(
                        f"Skipped line {m.line}, {m.label}: the sheet already has a SyntaxError"
                    )
        for v in variants:
            v.outcome = classify(baseline, runs[v.mutation])
            v.silent = runs_the_same(baseline, runs[v.mutation])
            ctx.log(f"Variant {v.number}: line {v.mutation.line}, {v.mutation.label} → {v.outcome}")
        if not variants:
            if dropped:
                raise ToolError(
                    "Every possible bug leaves this program's output unchanged. Raise "
                    "“Silent bugs allowed” to make a read-the-code sheet anyway."
                )
            raise ToolError("No suitable lines for the chosen error classes.")
        silent = sum(v.silent for v in variants)
        visible = len(variants) - silent
        if len(variants) < options.count:
            if dropped:
                ctx.warn(
                    f"Only {visible} distinct bugs change what this program does; asked for "
                    f"{options.count}. {len(dropped)} more would run the same as the original. "
                    "Raise “Silent bugs allowed” to keep some for a read-the-code discussion."
                )
            else:
                ctx.warn(
                    f"Only {len(variants)} distinct mutations possible; asked for {options.count}."
                )
        # The selection looks for a wrong-output bug only with something visible
        # to swap out; then it has tried every candidate before giving up.
        if (
            len(variants) >= 2
            and visible
            and "wrong_output" not in outcomes
            and not any(outcome_kind(baseline, r) == "wrong_output" for r in runs.values())
        ):
            more = len(options.kinds()) < len(logic.KIND_LABELS)
            ctx.warn(
                "None of the possible bugs in this program runs with the wrong output; "
                "every version crashes, hangs or runs the same."
                + (" Ticking more error classes may give one." if more else "")
            )
        if syntax > 1:
            ctx.warn(
                f"{syntax} of the {len(variants)} versions stop with a SyntaxError before "
                "they start: there were not enough other bugs to make up the number."
            )
        if silent:
            ctx.warn(
                f"{silent} of the {len(variants)} versions {'runs' if silent == 1 else 'run'} "
                "exactly like the original; "
                "the sheet tells pupils to read the code."
            )

        ctx.progress(0.85, "Writing files")
        out = ctx.output_dir
        out.mkdir(parents=True, exist_ok=True)
        files = []
        for v in variants:
            path = out / f"{name}_bug{v.number}.py"
            path.write_text(v.source, encoding="utf-8")
            files.append(path)
        doc = build_document(name, source, variants, seed=options.seed)
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
        sheet_text, key_text = to_text(doc.sheet()), to_text(doc.key())
        return RunResult(
            tables={"key": key},
            texts={"preview": sheet_text + "\n\n" + key_text},  # the CLI's --preview
            pages={"pages": pages_from(files, sheet_text=sheet_text, key_text=key_text)},
            files=files,
            summary=f"{len(variants)} variants written to {out}",
            outcome=f"{len(variants)} buggy versions"
            + (f" (asked for {options.count})" if len(variants) < options.count else "")
            + (f" · {silent} silent" if silent else "")
            + f" · seed {options.seed} · lines "
            + ", ".join(str(v.mutation.line) for v in variants),
        )


plugin = BugsPlugin()
