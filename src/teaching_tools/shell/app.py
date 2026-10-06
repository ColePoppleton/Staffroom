"""``tt-gui`` entry point.

Hidden flags make the launcher scriptable for docs and tests::

    tt-gui --tool hello --open examples/marks_10x.csv --run --screenshot docs/launcher.png
    tt-gui --resource "Python/OCR Booklet/9a.py" --screenshot docs/library.png
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from teaching_tools import __version__
from teaching_tools.core.config import load_config
from teaching_tools.core.log import get_logger, setup_logging
from teaching_tools.shell.main_window import MainWindow

log = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="tt-gui", description="Teaching Tools launcher")
    parser.add_argument("--tool", help="tool to open on start")
    parser.add_argument("--open", type=Path, help="file to load into the tool's first file picker")
    parser.add_argument(
        "--resource", help="open the Resources view on this path (relative to root)"
    )
    parser.add_argument("--theme", choices=["dark", "light"], help="override the saved theme")
    parser.add_argument("--run", action="store_true", help="run the tool before --screenshot")
    parser.add_argument("--screenshot", type=Path, help="render, save a PNG, and exit")
    parser.add_argument("--size", default="1240x780", help="window size for --screenshot, WxH")
    parser.add_argument("--version", action="version", version=__version__)
    return parser.parse_args(argv)


def build_window(args: argparse.Namespace) -> MainWindow:
    config = load_config()
    if args.theme:
        config.general.theme = args.theme
    if args.screenshot:
        config.read_only = True
    window = MainWindow(config)
    if args.tool:
        window.sidebar.select(args.tool)
    if args.open and args.tool:
        panel = window.panel_for(args.tool)
        key = panel.first_file_key()
        if key:
            panel.set_input_path(key, args.open.resolve())
    if args.resource is not None:
        window.sidebar.set_mode("resources")
        if args.resource:
            window.sidebar.resources.select(args.resource)
    return window


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.screenshot:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    config = load_config()
    setup_logging(config.general.log_level, stderr=False)

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(sys.argv[:1])
    app.setApplicationName("Teaching Tools")
    app.setOrganizationName("teaching-tools")
    window = build_window(args)

    if args.screenshot:
        width, height = (int(x) for x in args.size.lower().split("x"))
        window.resize(width, height)
        window.show()
        if args.run and args.tool:
            panel = window.panel_for(args.tool)
            panel.run_finished.connect(
                lambda _ok: QTimer.singleShot(
                    200, lambda: _save_screenshot(app, window, args.screenshot)
                )
            )
            QTimer.singleShot(200, panel.start_run)
        else:
            QTimer.singleShot(400, lambda: _save_screenshot(app, window, args.screenshot))
        return app.exec()

    window.show()
    log.info("launcher started")
    return app.exec()


def _save_screenshot(app: QApplication, window: MainWindow, path: Path) -> None:
    app.processEvents()
    path.parent.mkdir(parents=True, exist_ok=True)
    ok = window.grab().save(str(path))
    print(("saved " if ok else "FAILED to save ") + str(path))
    app.exit(0 if ok else 1)


if __name__ == "__main__":
    raise SystemExit(main())
