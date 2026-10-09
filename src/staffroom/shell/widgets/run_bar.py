"""The foot of the inputs pane: the run button with its ⌘↵ hint, where the
run will write, the status line and a thin progress bar along the top edge."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.panel import DEFAULT_OPEN_LABEL, DEFAULT_WRITES_VERB
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
        open_label: str = DEFAULT_OPEN_LABEL,
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

        body = QVBoxLayout()
        body.setContentsMargins(22, 12, 22, 14)
        body.setSpacing(8)
        outer.addLayout(body)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.button = QPushButton(label)
        self.button.setProperty("role", "primary")
        self.button.setDefault(True)
        self.button.setToolTip(f"{label} ({RUN_SHORTCUT_TEXT})")
        self.button.clicked.connect(self.run_requested.emit)
        self.shortcut_hint = QLabel(RUN_SHORTCUT_TEXT)
        self.shortcut_hint.setProperty("role", "faint")
        row.addWidget(self.button)
        row.addWidget(self.shortcut_hint)
        row.addStretch(1)
        body.addLayout(row)

        # Where the run will write, shown before Run so nobody has to guess.
        folder_row = QHBoxLayout()
        folder_row.setSpacing(8)
        self.folder = ElidedLabel(mode=Qt.TextElideMode.ElideMiddle, auto_tooltip=False)
        self.folder.setProperty("role", "faint")
        self.folder.hide()
        self.open_folder = QPushButton(open_label)
        self.open_folder.setProperty("role", "link")
        self.open_folder.clicked.connect(self._open_folder)
        self.open_folder.hide()
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(self.open_folder)
        body.addLayout(folder_row)

        # Two lines at most; a long summary (every file written) is elided and
        # kept whole in the tooltip and the log.
        self.status = ElidedLabel("Ready", max_lines=2)
        self.status.setProperty("role", "muted")
        body.addWidget(self.status)

    def set_running(self, running: bool) -> None:
        self.button.setEnabled(not running)
        self.progress.setValue(0)  # the bar is a hairline again once the run is over
        if running:
            self.set_status("Running…")

    def set_progress(self, fraction: float, message: str) -> None:
        self.progress.setValue(int(max(0.0, min(1.0, fraction)) * 1000))
        if message:
            self.set_status(message)

    def set_status(self, text: str, role: str = "muted") -> None:
        self.status.setText(text)
        self.status.setProperty("role", role)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def set_output_folder(self, folder: Path | None) -> None:
        """Show where outputs go. Called before a run with the resolved default
        and again after a successful run with where the files actually went."""
        self._folder = folder
        if folder is None:
            self.folder.clear()
            self.folder.setToolTip("")
        else:
            self.folder.setText(f"{self._verb} {abbreviate_path(folder)}")
            self.folder.setToolTip(str(folder))
        self.folder.setVisible(folder is not None)
        self.open_folder.setVisible(folder is not None)

    def _open_folder(self) -> None:
        if self._folder:
            # The default folder may not exist until the first write; make it
            # so the link works before the first run too.
            self._folder.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._folder)))


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
