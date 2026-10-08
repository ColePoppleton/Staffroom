"""Fade: a worked solution → progressively faded completion problems."""

from __future__ import annotations

from typing import Any

from staffroom.core.codeinput import code_from_inputs
from staffroom.core.export import export, house_style_from, to_text
from staffroom.core.panel import PanelSpec
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

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.fade.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        options: logic.Options = inputs.get("options", logic.Options())
        try:
            source, name = code_from_inputs(inputs)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        try:
            versions = logic.fade_versions(source, options)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
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
        return RunResult(
            texts={"preview": to_text(doc.sheet()) + "\n\n" + to_text(doc.key())},
            files=files,
            summary=f"Wrote {', '.join(f.name for f in files)} to {ctx.output_dir}",
        )


plugin = FadePlugin()
