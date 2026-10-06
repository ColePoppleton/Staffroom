"""A bottom dock that mirrors the ``teaching_tools`` logger."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from teaching_tools.core.log import DATEFMT, FORMAT, ROOT_LOGGER


class _Bridge(QObject):
    line = Signal(str)


class QtLogHandler(logging.Handler):
    """Thread-safe: records arrive from worker threads and cross to the GUI
    thread through a queued signal."""

    def __init__(self) -> None:
        super().__init__()
        self.bridge = _Bridge()
        self.setFormatter(logging.Formatter(FORMAT, DATEFMT))

    def emit(self, record: logging.LogRecord) -> None:
        self.bridge.line.emit(self.format(record))


class LogDrawer(QDockWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Log", parent)
        self.setObjectName("LogDrawer")
        self.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        body = QWidget()
        body.setObjectName("DockBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(8)
        self.view = QPlainTextEdit()
        self.view.setObjectName("LogView")
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(5000)
        row = QHBoxLayout()
        clear = QPushButton("Clear")
        clear.setProperty("role", "ghost")
        clear.clicked.connect(self.view.clear)
        row.addStretch(1)
        row.addWidget(clear)
        layout.addWidget(self.view, 1)
        layout.addLayout(row)
        self.setWidget(body)
        self.setMinimumHeight(160)

        self.handler = QtLogHandler()
        self.handler.bridge.line.connect(self.view.appendPlainText)
        logging.getLogger(ROOT_LOGGER).addHandler(self.handler)
        self.hide()

    def closeEvent(self, event: object) -> None:  # noqa: N802
        logging.getLogger(ROOT_LOGGER).removeHandler(self.handler)
        super().closeEvent(event)  # type: ignore[arg-type]
