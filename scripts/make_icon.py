"""Render the Staffroom mark (``shell/assets/mark.svg``, the door ajar) into
every raster the project needs, with Qt's SVG renderer so the icon and the
launcher agree pixel for pixel:

* ``src/staffroom/shell/assets/icon.png``  512 px, the Qt window icon
* ``src/staffroom/shell/assets/icon.icns`` the .app bundle icon (via iconutil)
* ``docs/assets/icon.png``                 512 px, the docs site logo
* ``docs/assets/favicon.png``              32 px

The app icons keep a transparent inset: macOS expects the artwork to fill
about 80 % of the canvas (on a 1024 canvas the tile spans 824 px, centred)
and draws a full-bleed icon oversized next to other apps. The web assets are
full-bleed, which is what a logo slot and a favicon want.

Run with: uv run python scripts/make_icon.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "staffroom" / "shell" / "assets"
MARK = ASSETS / "mark.svg"
DOCS_ASSETS = ROOT / "docs" / "assets"

ICONSET_SIZES = (16, 32, 128, 256, 512)
# Apple's icon grid: on a 1024 px canvas the tile is 824 px wide, centred.
APP_ICON_CANVAS = 1024
APP_ICON_TILE = 824


def render(renderer: QSvgRenderer, size: int, *, inset: bool = False) -> QImage:
    """Render the mark on a transparent ``size`` x ``size`` canvas. With
    ``inset`` the tile is scaled to the app-icon grid and centred."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    if inset:
        tile = size * APP_ICON_TILE / APP_ICON_CANVAS
        offset = (size - tile) / 2
        renderer.render(painter, QRectF(offset, offset, tile, tile))
    else:
        renderer.render(painter)
    painter.end()
    return image


def save(image: QImage, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(path), "PNG"):
        raise SystemExit(f"could not write {path}")
    print("wrote", path.relative_to(ROOT))


def main() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    renderer = QSvgRenderer(str(MARK))
    if not renderer.isValid():
        raise SystemExit(f"cannot read {MARK}")
    renderer.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)

    save(render(renderer, 512, inset=True), ASSETS / "icon.png")
    save(render(renderer, 512), DOCS_ASSETS / "icon.png")
    save(render(renderer, 32), DOCS_ASSETS / "favicon.png")

    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for base in ICONSET_SIZES:
            render(renderer, base, inset=True).save(str(iconset / f"icon_{base}x{base}.png"), "PNG")
            render(renderer, base * 2, inset=True).save(
                str(iconset / f"icon_{base}x{base}@2x.png"), "PNG"
            )
        if shutil.which("iconutil"):
            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "icon.icns")],
                check=True,
            )
            print("wrote", (ASSETS / "icon.icns").relative_to(ROOT))
        else:
            print("iconutil not found; icon.icns left as is")
    del app


if __name__ == "__main__":
    main()
