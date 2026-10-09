"""Shows a PNG (e.g. a chart) scaled to fit the space it is given, keeping aspect.

Two labels in a stack: a styled empty-state and a bare image label. Keeping
them separate matters: a stylesheet padding applied for the empty state would
otherwise linger on the image label and clip the picture's edges. The image
label ignores the pixmap for sizing, so a 1200 px chart never stretches the
panel; it is fitted, width and height, to whatever box the layout gives it
(a tab in the output pane, which fills the window)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QStackedLayout, QWidget

MIN_HEIGHT = 160


class _ImageLabel(QLabel):
    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(120, 80)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(480, 320)


class ImageViewWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumHeight(MIN_HEIGHT)
        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.empty = QLabel("No image yet.")
        self.empty.setProperty("role", "empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image = _ImageLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.image)
        self.set_image(None)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(480, 320)

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
            return
        self._pixmap = pixmap
        self.stack.setCurrentWidget(self.image)
        self._rescale()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._pixmap is not None and event.size() != event.oldSize():
            self._rescale()

    def _rescale(self) -> None:
        if self._pixmap is None:
            return
        scaled = self._pixmap.scaled(
            max(self.width(), 120),
            max(self.height(), 80),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image.setPixmap(scaled)
