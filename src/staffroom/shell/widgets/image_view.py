"""Shows a picture (a chart PNG, a photo, a PDF page) scaled to fit the space
it is given, keeping aspect.

Two labels in a stack: a styled empty-state and a bare image label. Keeping
them separate matters: a stylesheet padding applied for the empty state would
otherwise linger on the image label and clip the picture's edges. The image
label ignores the pixmap for sizing, so a 1200 px chart never stretches the
panel; it is fitted, width and height, to whatever box the layout gives it
(a tab in the output pane, which fills the window).

Resizing stays smooth (#64): while the size is changing the picture is
rescaled with a fast transform, and once it has stopped for
:data:`SETTLE_MS` with a smooth one, after which :attr:`settled` fires (the
Library preview then decides whether a sharper copy is worth drawing). The
picture is drawn at the screen's device pixel ratio, so it is crisp on a
Retina display.

:meth:`set_image` reads a file on the calling thread: fine for a tool's
chart, too slow for a 12-megapixel photo. The Library preview decodes off
the GUI thread instead and hands the result to :meth:`set_picture`."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QStackedLayout, QWidget

MIN_HEIGHT = 160
SETTLE_MS = 150  # quiet time after the last resize before the smooth redraw


class _ImageLabel(QLabel):
    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(120, 80)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(480, 320)


class ImageViewWidget(QWidget):
    settled = Signal()  # the size stopped changing and the picture was redrawn smoothly

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setMinimumHeight(MIN_HEIGHT)
        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.empty = QLabel("No image yet.")
        self.empty.setProperty("role", "empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.image = _ImageLabel()
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.image)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self._on_settled)
        self.set_image(None)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(480, 320)

    def pixmap(self) -> QPixmap | None:
        return self.image.pixmap() if self._image is not None else None

    def picture(self) -> QImage | None:
        """The picture on show, at the size it was handed over (None: none)."""
        return self._image

    def set_image(self, path: Path | None) -> None:
        image = QImage(str(path)) if path is not None and path.exists() else QImage()
        if image.isNull():
            if path is None:
                self.show_message("No image yet.")
            else:
                self.show_message(f"Could not load {path.name}")
            return
        self.set_picture(image)

    def set_picture(self, image: QImage) -> None:
        """Show ``image`` (decoded already), fitted to the space."""
        if image.isNull():
            self.show_message("Could not show this picture")
            return
        self._image = image
        self.stack.setCurrentWidget(self.image)
        self._rescale(smooth=True)

    def show_message(self, text: str) -> None:
        """No picture: ``text`` in the quiet empty state (``"Loading…"``,
        ``"Could not load …"``)."""
        self._image = None
        self._settle.stop()
        self.image.clear()
        self.empty.setText(text)
        self.stack.setCurrentWidget(self.empty)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self._image is not None and event.size() != event.oldSize():
            self._rescale(smooth=False)
            self._settle.start()

    def target_size(self) -> QSize:
        """The space for the picture, in device pixels."""
        ratio = self.devicePixelRatioF()
        return QSize(round(max(self.width(), 120) * ratio), round(max(self.height(), 80) * ratio))

    def _on_settled(self) -> None:
        self._rescale(smooth=True)
        self.settled.emit()

    def _rescale(self, *, smooth: bool) -> None:
        if self._image is None:
            return
        mode = (
            Qt.TransformationMode.SmoothTransformation
            if smooth
            else Qt.TransformationMode.FastTransformation
        )
        scaled = self._image.scaled(self.target_size(), Qt.AspectRatioMode.KeepAspectRatio, mode)
        pixmap = QPixmap.fromImage(scaled)
        pixmap.setDevicePixelRatio(self.devicePixelRatioF())
        self.image.setPixmap(pixmap)
