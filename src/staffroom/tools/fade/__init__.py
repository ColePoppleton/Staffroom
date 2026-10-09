"""Fade: a worked solution → progressively faded completion problems."""

from __future__ import annotations

from typing import Any

from staffroom.core.codeinput import code_from_inputs
from staffroom.core.export import export, house_style_from, to_text
from staffroom.core.panel import PanelSpec, pages_from
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.tools.fade import logic
from staffroom.tools.fade.panel import panel_spec
from staffroom.tools.fade.sheet import build_document


def formats_for(choice: str) -> tuple[str, ...]:
    return ("docx", "pdf") if choice == "both" else (choice,)


class FadePlugin:
    name = "fade"
    description = "Worked solution → progressively faded versions with the solution as key."
    version = "0.1.0"
    group, glyph = "From a program", "taper"  # sidebar group and glyph (#89)

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.fade.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options", logic.Options())
        source, name = code_from_inputs(inputs)
        try:
            versions = logic.fade_versions(source, options)
        except SyntaxError as exc:
            raise ToolError(f"That is not valid Python: {exc.msg} (line {exc.lineno})") from exc
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        for _line, why in logic.unfadeable_lines(source, options):
            ctx.log(f"Skipped: {why}")
        if len(versions) < options.steps:
            ctx.log(
                f"Asked for {options.steps} versions but only {len(versions)} "
                f"line{'s' if len(versions) != 1 else ''} can fade, so made {len(versions)} "
                "(one more blank each time)."
            )
        ctx.log(
            f"{len(versions)} versions; blanks per version: "
            + ", ".join(str(logic.blank_count(v)) for v in versions)
        )
        doc = build_document(name, source, versions)
        ctx.progress(0.6, "Writing files")
        files = export(
            doc,
            ctx.output_dir,
            f"{name}_faded",
            formats_for(options.formats),
            style=house_style_from(ctx.config),
        )
        ctx.progress(1.0, "Done")
        sheet_text, key_text = to_text(doc.sheet()), to_text(doc.key())
        return RunResult(
            texts={"preview": sheet_text + "\n\n" + key_text},  # the CLI's --preview
            pages={"pages": pages_from(files, sheet_text=sheet_text, key_text=key_text)},
            files=files,
            summary=f"Wrote {', '.join(f.name for f in files)} to {ctx.output_dir}",
            outcome=f"{len(versions)} versions · blanks "
            + ", ".join(str(logic.blank_count(v)) for v in versions),
        )


plugin = FadePlugin()
