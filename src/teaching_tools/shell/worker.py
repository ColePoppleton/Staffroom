"""Runs a tool off the GUI thread and reports back through signals."""

from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from teaching_tools.core.config import Config
from teaching_tools.core.library.service import ResourceService
from teaching_tools.core.plugin import Inputs, RunContext, ToolError, ToolPlugin


class RunWorker(QThread):
    progress = Signal(float, str)
    log = Signal(str)
    succeeded = Signal(object)  # RunResult
    failed = Signal(str, bool)  # message, is_bug

    def __init__(
        self,
        plugin: ToolPlugin,
        inputs: Inputs,
        config: Config,
        output_dir: Path,
        resources: ResourceService | None = None,
    ) -> None:
        super().__init__()
        self.plugin = plugin
        self.inputs = inputs
        self.config = config
        self.output_dir = output_dir
        self.resources = resources

    def run(self) -> None:
        ctx = RunContext(
            config=self.config,
            output_dir=self.output_dir,
            progress=lambda f, m: self.progress.emit(f, m),
            log=lambda m: self.log.emit(m),
            resources=self.resources,
        )
        try:
            result = self.plugin.run(self.inputs, ctx)
        except ToolError as exc:
            self.failed.emit(str(exc), False)
        except Exception:
            self.failed.emit(traceback.format_exc(), True)
        else:
            self.succeeded.emit(result)
