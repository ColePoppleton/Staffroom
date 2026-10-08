"""Draw the app icon with Pillow and build icon.png (for Qt) and icon.icns
(for the .app bundle via iconutil). Run with: uv run python scripts/make_icon.py"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parents[1] / "src" / "teaching_tools" / "shell" / "assets"
ACCENT = (109, 141, 255)
ACCENT_DARK = (59, 91, 219)
INK = (15, 17, 21)
PAPER = (255, 255, 255)


def draw(size: int) -> Image.Image:
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(s * 0.22)
    # macOS-style rounded square, accent gradient faked with two layers.
    d.rounded_rectangle((0, 0, s - 1, s - 1), radius=radius, fill=ACCENT_DARK)
    d.rounded_rectangle((0, 0, s - 1, int(s * 0.92)), radius=radius, fill=ACCENT)
    # A "sheet" with three lines: worksheets are what the app makes.
    m = int(s * 0.24)
    sheet = (m, int(s * 0.18), s - m, s - int(s * 0.16))
    d.rounded_rectangle(sheet, radius=int(s * 0.06), fill=PAPER)
    line_x0, line_x1 = sheet[0] + int(s * 0.08), sheet[2] - int(s * 0.08)
    for i, frac in enumerate((0.36, 0.48, 0.60)):
        y = int(s * frac)
        width = line_x1 if i != 2 else line_x0 + int((line_x1 - line_x0) * 0.6)
        d.rounded_rectangle(
            (line_x0, y, width, y + max(2, int(s * 0.045))), radius=int(s * 0.02), fill=INK
        )
    # A tick in the corner: marked work.
    tick_w = max(3, int(s * 0.06))
    cx, cy = s - int(s * 0.30), s - int(s * 0.30)
    d.line(
        [
            (cx - int(s * 0.10), cy),
            (cx - int(s * 0.02), cy + int(s * 0.08)),
            (cx + int(s * 0.14), cy - int(s * 0.10)),
        ],
        fill=ACCENT_DARK,
        width=tick_w,
        joint="curve",
    )
    return img


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    draw(512).save(ASSETS / "icon.png")
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            draw(base).save(iconset / f"icon_{base}x{base}.png")
            draw(base * 2).save(iconset / f"icon_{base}x{base}@2x.png")
        if shutil.which("iconutil"):
            subprocess.run(
                ["iconutil", "-c", "icns", str(iconset), "-o", str(ASSETS / "icon.icns")],
                check=True,
            )
            print("wrote", ASSETS / "icon.icns")
    print("wrote", ASSETS / "icon.png")


if __name__ == "__main__":
    main()
