"""The foot of the inputs pane: the run button, its ⌘↵ hint and, under the
hint, where the next run will write; a thin progress bar runs along the top
edge. How the run went is the result strip's job (top of the output pane),
so nothing here repeats it."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.panel import DEFAULT_WRITES_VERB
from staffroom.shell.widgets.elided_label import ElidedLabel

# Qt maps Ctrl to Command on the Mac, so this is ⌘↵ there and Ctrl+↵ elsewhere.
RUN_SHORTCUTS = ("Ctrl+Return", "Ctrl+Enter")
RUN_SHORTCUT_TEXT = "⌘↵" if sys.platform == "darwin" else "Ctrl+↵"


class RunBar(QWidget):
    run_requested = Signal()

    def __init__(
        self,
        label: str = "Run",
        parent: QWidget | None = None,
        *,
        verb: str = DEFAULT_WRITES_VERB,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("RunBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._folder: Path | None = None
        self._verb = verb
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.progress = QProgressBar()
        self.progress.setObjectName("RunProgress")
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        outer.addWidget(self.progress)

        row = QHBoxLayout()
        row.setContentsMargins(22, 14, 22, 16)
        row.setSpacing(12)
        outer.addLayout(row)
        self.button = QPushButton(label)
        self.button.setProperty("role", "primary")
        self.button.setDefault(True)
        self.button.setToolTip(f"{label} ({RUN_SHORTCUT_TEXT})")
        self.button.clicked.connect(self.run_requested.emit)
        row.addWidget(self.button, 0, Qt.AlignmentFlag.AlignVCenter)

        # The shortcut, and under it where the run will write: shown before
        # Run so nobody has to guess, and kept current as the inputs change.
        beside = QVBoxLayout()
        beside.setSpacing(1)
        self.shortcut_hint = QLabel(RUN_SHORTCUT_TEXT)
        self.shortcut_hint.setProperty("role", "faint")
        self.folder = ElidedLabel(mode=Qt.TextElideMode.ElideMiddle, auto_tooltip=False)
        self.folder.setProperty("role", "faint")
        self.folder.hide()
        beside.addWidget(self.shortcut_hint)
        beside.addWidget(self.folder)
        row.addLayout(beside, 1)

    def set_running(self, running: bool) -> None:
        self.button.setEnabled(not running)
        self.progress.setValue(0)  # the bar is a hairline again once the run is over

    def set_progress(self, fraction: float, _message: str = "") -> None:
        self.progress.setValue(int(max(0.0, min(1.0, fraction)) * 1000))

    def set_output_folder(self, folder: Path | None) -> None:
        """Show where the next run's files go (the panel calls this whenever
        an input that decides it changes)."""
        self._folder = folder
        if folder is None:
            self.folder.setText("")
            self.folder.setToolTip("")
        else:
            self.folder.setText(f"{self._verb} {abbreviate_path(folder)}")
            self.folder.setToolTip(str(folder))
        self.folder.setVisible(folder is not None)


def abbreviate_path(path: Path, limit: int = 44) -> str:
    """``~`` for the home folder, then the middle elided to fit a status row."""
    text = str(path)
    home = str(Path.home())
    if text == home or text.startswith(home + "/"):
        text = "~" + text[len(home) :]
    if len(text) <= limit:
        return text
    head = text[: limit // 3]
    tail = text[-(limit - len(head) - 1) :]
    return f"{head}…{tail}"
