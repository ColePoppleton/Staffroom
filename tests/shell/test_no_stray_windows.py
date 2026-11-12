"""Opening a tool, the Library or Settings shows nothing as a window of its own.

A widget with no parent that is told to show becomes a top-level window, if only
for a moment. On macOS that is a black flash, and in full screen the window
manager switches away from Staffroom. Widgets are hidden while they should be
hidden, and shown only once they sit in a layout inside the main window."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from staffroom.core.config import load_config
from staffroom.shell.main_window import MainWindow


class _WindowSpy(QObject):
    """Records every widget other than ``main`` that is shown as a window."""

    def __init__(self) -> None:
        super().__init__()
        self.main: QWidget | None = None
        self.where = "startup"
        self.seen: list[str] = []

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.Show
            and isinstance(obj, QWidget)
            and obj.isWindow()
            and obj is not self.main
        ):
            self.seen.append(f"{self.where}: {type(obj).__name__} {obj.objectName()!r}")
        return False


@pytest.fixture
def spy(qtbot: QtBot) -> _WindowSpy:
    app = QApplication.instance()
    assert app is not None
    watcher = _WindowSpy()
    app.installEventFilter(watcher)
    yield watcher
    app.removeEventFilter(watcher)


def test_opening_every_page_shows_no_stray_window(
    qtbot: QtBot, tmp_path: Path, spy: _WindowSpy
) -> None:
    config = load_config()
    config.general.output_dir = str(tmp_path / "out")
    config.general.resources_root = str(tmp_path / "resources")
    win = MainWindow(config, auto_index=False)
    spy.main = win
    qtbot.addWidget(win)
    win.show()
    qtbot.wait(20)

    for plugin in win.plugins:
        spy.where = plugin.name
        win.show_tool(plugin.name)
        qtbot.wait(10)
    spy.where = "library"
    win.show_library()
    qtbot.wait(10)
    spy.where = "settings"
    win.show_settings()
    qtbot.wait(10)

    assert win.plugins, "no tools were discovered"
    assert spy.seen == []
