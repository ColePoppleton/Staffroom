"""Runs a tool off the GUI thread and reports back through signals."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from staffroom.core.config import Config
from staffroom.core.library.service import ResourceService
from staffroom.core.plugin import Inputs, RunContext, RunResult, ToolError, ToolPlugin
from staffroom.core.usage import record_run

Job = Callable[[RunContext], RunResult]


class RunWorker(QThread):
    progress = Signal(float, str)
    log = Signal(str)
    warned = Signal(str)  # a ctx.warn() message (also logged)
    succeeded = Signal(object)  # RunResult
    failed = Signal(str, bool, object)  # message, is_bug, the ToolError (None for a bug)

    def __init__(
        self,
        plugin: ToolPlugin,
        inputs: Inputs,
        config: Config,
        output_dir: Path,
        resources: ResourceService | None = None,
        job: Job | None = None,
    ) -> None:
        super().__init__()
        self.plugin = plugin
        self.inputs = inputs
        self.config = config
        self.output_dir = output_dir
        self.resources = resources
        self.job: Job = job or (lambda ctx: plugin.run(inputs, ctx))
        self.job_is_run = job is None

    def run(self) -> None:
        ctx = RunContext(
            config=self.config,
            output_dir=self.output_dir,
            progress=lambda f, m: self.progress.emit(f, m),
            log=lambda m: self.log.emit(m),
            warned=lambda m: self.warned.emit(m),
            resources=self.resources,
        )
        try:
            result = self.job(ctx)
            if self.job_is_run:
                record_run(self.plugin.name)
        except ToolError as exc:
            self.failed.emit(str(exc), False, exc)
        except Exception:
            self.failed.emit(traceback.format_exc(), True, None)
        else:
            self.succeeded.emit(result)
