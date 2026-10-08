"""The app icon keeps the macOS inset so it is not drawn oversized next to
other apps; the web assets stay full-bleed."""

from pathlib import Path

from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
APP_ICON = ROOT / "src" / "staffroom" / "shell" / "assets" / "icon.png"
DOCS_ICON = ROOT / "docs" / "assets" / "icon.png"


def alpha_bbox(image: QImage) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the opaque pixels, inclusive."""
    w, h = image.width(), image.height()
    xs = [x for x in range(w) for y in range(h) if image.pixelColor(x, y).alpha() > 8]
    ys = [y for y in range(h) for x in range(w) if image.pixelColor(x, y).alpha() > 8]
    return min(xs), min(ys), max(xs), max(ys)


def test_app_icon_has_transparent_inset() -> None:
    image = QImage(str(APP_ICON))
    assert image.width() == 512 and image.height() == 512
    left, top, right, bottom = alpha_bbox(image)
    minimum = int(512 * 0.08)
    assert left >= minimum and top >= minimum
    assert 511 - right >= minimum and 511 - bottom >= minimum


def test_docs_icon_is_full_bleed() -> None:
    image = QImage(str(DOCS_ICON))
    left, top, right, bottom = alpha_bbox(image)
    assert (left, top) == (0, 0) or left + top < 4
    assert right >= 508 and bottom >= 508
