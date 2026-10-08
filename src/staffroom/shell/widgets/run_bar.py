"""The run button, progress bar and status line that sit under every panel."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget


class RunBar(QWidget):
    run_requested = Signal()

    def __init__(self, label: str = "Run", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._folder: Path | None = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.button = QPushButton(label)
        self.button.setProperty("role", "primary")
        self.button.setDefault(True)
        self.button.clicked.connect(self.run_requested.emit)
        self.status = QLabel("Ready")
        self.status.setProperty("role", "muted")
        self.open_folder = QPushButton("Open output folder")
        self.open_folder.setProperty("role", "link")
        self.open_folder.clicked.connect(self._open_folder)
        self.open_folder.hide()
        row.addWidget(self.button)
        row.addWidget(self.status, 1)
        row.addWidget(self.open_folder)
        outer.addLayout(row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        outer.addWidget(self.progress)

    def set_running(self, running: bool) -> None:
        self.button.setEnabled(not running)
        if running:
            self.open_folder.hide()
            self.set_status("Running…")
            self.progress.setValue(0)

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
        self._folder = folder
        self.open_folder.setVisible(folder is not None)

    def _open_folder(self) -> None:
        if self._folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._folder)))
