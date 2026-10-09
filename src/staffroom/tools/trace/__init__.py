"""Trace: run a program under sys.settrace in the sandbox and produce trace tables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from staffroom.core.codeinput import code_from_inputs
from staffroom.core.export import export, house_style_from, to_text
from staffroom.core.panel import PanelSpec
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.core.runner import MAX_OUTPUT_BYTES, blocked_imports, run_source
from staffroom.tools.trace import logic
from staffroom.tools.trace.panel import panel_spec
from staffroom.tools.trace.sheet import build_document

TRACER = Path(__file__).with_name("tracer_script.py").read_text(encoding="utf-8")
TIMEOUT = logic.TIMEOUT


def formats_for(choice: str) -> tuple[str, ...]:
    return ("docx", "pdf") if choice == "both" else (choice,)


def run_trace(
    source: str, stdin: str, max_steps: int, timeout: float = TIMEOUT
) -> logic.TraceResult:
    """Execute ``source`` under the tracer in the sandbox. Raises ToolError
    for refused imports, timeouts or a broken tracer run."""
    blocked = blocked_imports(source)
    if blocked:
        raise ToolError("Refusing to run: the program imports " + ", ".join(blocked))
    outcome = run_source(
        TRACER,
        filename="tt_tracer.py",
        extra_files={"program.py": source},
        argv=["program.py", str(max_steps)],
        stdin=stdin,
        timeout=timeout,
        # The tracer caps the program's own output at MAX_OUTPUT_BYTES characters
        # itself; its JSON payload (rows + escaped output) needs headroom above that.
        output_limit=4 * MAX_OUTPUT_BYTES,
    )
    if outcome.timed_out:
        raise ToolError(f"The program did not finish within {timeout:.0f}s (infinite loop?).")
    if outcome.stdout_truncated:
        raise ToolError(
            "The trace is too large to read back (over "
            f"{outcome.output_limit // 1024} KB). Lower Max steps or trim the program's output."
        )
    if outcome.returncode != 0 or not outcome.stdout.strip():
        detail = outcome.stderr.strip().splitlines()[-1] if outcome.stderr.strip() else "no output"
        raise ToolError(f"Could not trace the program: {detail}")
    try:
        payload = json.loads(outcome.stdout.strip().splitlines()[-1])
    except ValueError as exc:
        raise ToolError("The tracer returned something unreadable.") from exc
    return logic.parse_payload(payload)


class TracePlugin:
    name = "trace"
    description = "Blank and completed trace tables from a sandboxed run."
    version = "0.1.0"

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.trace.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options", logic.Options())
        source, name = code_from_inputs(inputs)
        stdin = str(inputs.get("stdin") or "")
        if stdin and not stdin.endswith("\n"):
            stdin += "\n"
        ctx.progress(0.2, "Running in the sandbox")
        result = run_trace(source, stdin, options.max_steps)
        if result.input_eof:
            # Nothing is written: a one-row sheet for a program that never got
            # its input is not a worksheet, it is a mistake to fix and rerun.
            raise ToolError(logic.missing_input_message(name, stdin, result.inputs_read))
        steps = logic.select_steps(
            result, source, options.kinds(), top_level_only=options.top_level_only
        )
        variables = logic.chosen_variables(
            result, options.variables, steps if options.top_level_only else None
        )
        preset = logic.preset_name(options)
        completed = logic.trace_table(steps, variables)
        blank = logic.trace_table(
            steps, variables, blank=True, line_numbers=options.blank_line_numbers
        )
        ctx.log(
            f"{preset}: {len(result.steps)} steps executed, {len(steps)} recorded; "
            f"variables: {', '.join(variables) or 'none'}"
            + (f"; ended with {result.error}" if result.error else "")
            + ("; capped" if result.truncated else "")
        )
        doc = build_document(
            name,
            source,
            blank,
            completed,
            result.stdout,
            truncated=result.truncated,
            error=result.error,
            preset=preset,
        )
        ctx.progress(0.7, "Writing files")
        files = export(
            doc,
            ctx.output_dir,
            f"{name}_trace",
            formats_for(options.formats),
            style=house_style_from(ctx.config),
        )
        ctx.progress(1.0, "Done")
        return RunResult(
            tables={"table": completed},
            texts={"preview": to_text(doc.sheet()) + "\n\n" + to_text(doc.key())},
            files=files,
            summary=(
                f"{len(steps)} rows"
                + (f"; ended with {result.error}" if result.error else "")
                + f"; wrote {', '.join(f.name for f in files)} to {ctx.output_dir}"
            ),
        )


plugin = TracePlugin()
