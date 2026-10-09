"""``staffroom`` entry point.

Hidden flags make the launcher scriptable for docs and tests::

    staffroom --tool hello --open examples/marks_10x.csv --run --screenshot docs/launcher.png
    staffroom --resource "Python/OCR Booklet/9a.py" --screenshot docs/library.png
"""

from __future__ import annotations

import argparse
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from staffroom import __version__
from staffroom.core.config import load_config
from staffroom.core.log import get_logger, setup_logging
from staffroom.shell.main_window import MainWindow
from staffroom.shell.tool_panel import ToolPanel

log = get_logger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="staffroom", description="Staffroom launcher")
    parser.add_argument("--tool", help="tool to open on start")
    parser.add_argument("--open", type=Path, help="file to load into the tool's first file picker")
    parser.add_argument("--resource", help="open the Library on this path (relative to root)")
    parser.add_argument("--settings", action="store_true", help="open the Settings page")
    parser.add_argument(
        "--first-run",
        action="store_true",
        help="show the first-run card as a fresh install would (the saved folder is kept)",
    )
    parser.add_argument("--theme", choices=["dark", "light"], help="override the saved theme")
    parser.add_argument(
        "--preset", help="choose this preset in the tool's options form (for --screenshot)"
    )
    parser.add_argument("--run", action="store_true", help="run the tool before --screenshot")
    parser.add_argument(
        "--expand",
        action="store_true",
        help="after --run, open the strip's warnings list (for --screenshot)",
    )
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
        # A screenshot run must not leave files next to the example input or
        # in the checkout: send its outputs to a folder that dies with it.
        config.general.output_dir = screenshot_output_dir()
    window = MainWindow(config, first_run=True if args.first_run else None)
    if args.tool:
        window.go_to_tool(args.tool)
    if args.open and args.tool:
        panel = window.panel_for(args.tool)
        key = panel.first_file_key()
        if key:
            panel.set_input_path(key, args.open.resolve())
    if args.preset and args.tool:
        for form in window.panel_for(args.tool).forms.values():
            form.apply_preset(args.preset)
    if args.resource is not None:
        window.show_library()
        if args.resource:
            window.resources.select(args.resource)
    if args.settings:
        window.show_settings()
    return window


def _expand(panel: ToolPanel) -> None:
    """Open the warnings list, so a screenshot shows each warning."""
    if panel.strip.warnings:
        panel.strip.warning_toggle.setChecked(True)


def screenshot_output_dir() -> str:
    """A fresh temporary output folder, removed when the process exits."""
    folder = tempfile.mkdtemp(prefix="staffroom-screenshot-")
    atexit.register(shutil.rmtree, folder, True)
    return folder


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.screenshot:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    config = load_config()
    setup_logging(config.general.log_level, stderr=False)

    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(sys.argv[:1])
    app.setApplicationName("Staffroom")
    app.setOrganizationName("staffroom")
    icon = Path(__file__).with_name("assets") / "icon.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = build_window(args)

    if args.screenshot:
        width, height = (int(x) for x in args.size.lower().split("x"))
        window.resize(width, height)
        window.show()
        if args.run and args.tool:
            panel = window.panel_for(args.tool)
            if args.expand:
                panel.run_finished.connect(lambda _ok: _expand(panel))
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
    # A first index may still be running (a fresh home, or a folder indexed
    # for the first time): stop it before the window goes, or Qt aborts the
    # process after the PNG is written (#40).
    window.wait_for_workers()
    app.exit(0 if ok else 1)


if __name__ == "__main__":
    raise SystemExit(main())
