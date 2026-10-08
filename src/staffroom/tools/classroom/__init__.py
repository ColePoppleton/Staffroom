"""Classroom: open a resource for a lesson on a copy, never the original."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from staffroom.core import paths
from staffroom.core.panel import PanelSpec
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError
from staffroom.tools.classroom import sessions
from staffroom.tools.classroom.logic import summarise_diff
from staffroom.tools.classroom.panel import panel_spec


class ClassroomPlugin:
    name = "classroom"
    description = "Open a resource for class on a copy; diff and promote edits."
    version = "0.1.0"

    def register_cli(self, app: Any) -> None:
        from staffroom.tools.classroom.cli import register

        register(app)

    def panel_spec(self) -> PanelSpec:
        return panel_spec()

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def sessions_root(ctx: RunContext) -> Path:
        return paths.sessions_root(ctx.config.general.sessions_root)

    def _sessions_result(self, ctx: RunContext, **extra: Any) -> RunResult:
        files = sessions.list_sessions(self.sessions_root(ctx))
        return RunResult(tables={"sessions": sessions.sessions_table(files)}, **extra)

    # -- run: open for class --------------------------------------------
    def run(self, inputs: Inputs, ctx: RunContext) -> RunResult:
        resource: Path | None = inputs.get("resource")
        if resource is None:
            raise ToolError("Pick a resource first.")
        try:
            copy, created = sessions.open_for_class(
                resource,
                str(inputs.get("label", "")),
                self.sessions_root(ctx),
                ctx.config.general.editor_command,
            )
        except (ValueError, FileNotFoundError) as exc:
            raise ToolError(str(exc)) from exc
        verb = "Copied" if created else "Re-opened existing copy"
        ctx.log(f"{verb}: {copy}")
        ctx.log(f"Editor: {ctx.config.general.editor_command}")
        return self._sessions_result(
            ctx, files=[copy], summary=f"{verb} {copy.name} in your editor"
        )

    # -- row actions -----------------------------------------------------
    def act(self, name: str, row: Mapping[str, Any], ctx: RunContext) -> RunResult:
        root = self.sessions_root(ctx)
        if name == "refresh":
            return self._sessions_result(ctx)
        ref = str(row.get("Session file") or "")
        if not ref:
            raise ToolError("Pick a session file first.")
        try:
            file = sessions.resolve_session_file(root, ref)
        except FileNotFoundError as exc:
            raise ToolError(str(exc)) from exc
        if name == "diff":
            diff = sessions.diff_against_original(file)
            return RunResult(texts={"diff": diff}, summary=f"{file.name}: {summarise_diff(diff)}")
        if name == "reopen":
            argv = sessions.reopen(file, ctx.config.general.editor_command)
            ctx.log("Launched: " + " ".join(argv))
            return RunResult(summary=f"Re-opened {file.name}")
        if name == "promote":
            resources_root = Path(ctx.config.general.resources_root).expanduser()
            try:
                target = sessions.promote(file, resources_root)
            except (ValueError, OSError) as exc:
                raise ToolError(str(exc)) from exc
            ctx.log(f"Promoted to {target}")
            return self._sessions_result(
                ctx, files=[target], summary=f"Promoted as {target.name} next to the original"
            )
        raise ToolError(f"Unknown action {name!r}")


plugin = ClassroomPlugin()
