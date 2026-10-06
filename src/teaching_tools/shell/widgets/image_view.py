"""Shows a PNG (e.g. a chart) scaled to fit, keeping aspect ratio."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget


class ImageViewWidget(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(200)
        self.set_image(None)

    def set_image(self, path: Path | None) -> None:
        if path is None or not path.exists():
            self._pixmap = None
            self.setProperty("role", "empty")
            self.setText("No image yet." if path is None else f"Missing image: {path.name}")
        else:
            self._pixmap = QPixmap(str(path))
            self.setProperty("role", "")
            self.setText("")
        self.style().unpolish(self)
        self.style().polish(self)
        self._rescale()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setPixmap(scaled)
