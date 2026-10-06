"""Shows a PNG (e.g. a chart) scaled to the available width, keeping aspect.

Two labels in a stack: a styled empty-state and a bare image label. Keeping
them separate matters: a stylesheet padding applied for the empty state would
otherwise linger on the image label and clip the picture's edges. The image
label ignores the pixmap for sizing, so a 1200 px chart never stretches the
panel; it is fitted to whatever width the layout gives it."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QStackedLayout, QWidget

MAX_HEIGHT = 560
EMPTY_HEIGHT = 200


class _ImageLabel(QLabel):
    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(120, 80)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(480, self.height() or EMPTY_HEIGHT)


class ImageViewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.empty = QLabel("No image yet.")
        self.empty.setProperty("role", "empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image = _ImageLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.image)
        self.set_image(None)

    def pixmap(self) -> QPixmap | None:
        return self.image.pixmap() if self._pixmap is not None else None

    def set_image(self, path: Path | None) -> None:
        pixmap = QPixmap(str(path)) if path is not None and path.exists() else QPixmap()
        if pixmap.isNull():
            self._pixmap = None
            if path is None:
                self.empty.setText("No image yet.")
            else:
                self.empty.setText(f"Could not load {path.name}")
            self.stack.setCurrentWidget(self.empty)
            self.setFixedHeight(EMPTY_HEIGHT)
            return
        self._pixmap = pixmap
        self.stack.setCurrentWidget(self.image)
        self._rescale()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._pixmap is not None and event.size().width() != event.oldSize().width():
            self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        width = max(self.width(), 120)
        height = min(int(width * self._pixmap.height() / max(self._pixmap.width(), 1)), MAX_HEIGHT)
        scaled = self._pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.setFixedHeight(scaled.height())
        self.image.setPixmap(scaled)
