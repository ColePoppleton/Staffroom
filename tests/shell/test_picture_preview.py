"""The Library preview draws pictures without freezing the window (#64).

Every file here is invented in the test: noise photos made with numpy and
Pillow, PDFs made with reportlab. Selecting a big photo or a long scanned PDF
must leave the GUI thread free (a timer keeps firing while the picture
loads), arrowing through many photos must never run more than one decode at
a time nor show anything but the last one, photos keep their orientation,
and a PDF shows its page as a picture with a page count and Previous / Next.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PIL import Image
from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QImage
from pytestqt.qtbot import QtBot
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from staffroom.core.config import load_config
from staffroom.core.library.service import LibraryService
from staffroom.shell.main_window import MainWindow
from staffroom.shell.widgets import picture_preview
from staffroom.shell.widgets.image_view import ImageViewWidget
from staffroom.shell.widgets.picture_preview import LOADING, PicturePreview

LOAD_TIMEOUT = 60_000  # ms: the Mac running the suite can be very busy


# ---------------------------------------------------------------- invented files
def noise_photo(path: Path, width: int, height: int, seed: int = 64) -> Path:
    """A photo-sized JPEG (or PNG, by suffix) of random noise: as slow to
    decode as a real photo, and nothing in it."""
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    Image.fromarray(pixels).save(path, quality=90)
    return path


def scanned_pdf(path: Path, pages: int, photo: Path | None = None) -> Path:
    """A PDF with no text layer, like a scanned booklet: each page a filled
    block (red on odd pages, blue on even) and, if given, the photo."""
    pdf = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    for page in range(pages):
        pdf.setFillColorRGB(*((0.9, 0.1, 0.1) if page % 2 == 0 else (0.1, 0.1, 0.9)))
        pdf.rect(0, 0, width, height, stroke=0, fill=1)
        if photo is not None:
            pdf.drawImage(str(photo), 60, 60, width=width - 120, height=(width - 120) * 0.75)
        pdf.showPage()
    pdf.save()
    return path


@pytest.fixture(scope="module")
def big_files(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """A 12-megapixel noise photo, as #64 measured, and a 40-page scanned PDF
    with a smaller one on every page (quicker to make), made once."""
    folder = tmp_path_factory.mktemp("big")
    photo = noise_photo(folder / "photo.jpg", 4032, 3024)
    scan = noise_photo(folder / "scan.jpg", 1200, 900, seed=65)
    return {"photo": photo, "pdf": scanned_pdf(folder / "booklet.pdf", 40, scan)}


@pytest.fixture
def window(
    qtbot: QtBot, service: LibraryService, resources_root: Path, big_files: dict[str, Path]
) -> MainWindow:
    big = resources_root / "Big"
    big.mkdir()
    for name, source in (("photo.jpg", big_files["photo"]), ("booklet.pdf", big_files["pdf"])):
        (big / name).write_bytes(source.read_bytes())
    service.index()
    config = load_config()
    config.general.resources_root = str(resources_root)
    win = MainWindow(config, library=service, auto_index=False)
    qtbot.addWidget(win)
    win.resize(1100, 760)
    win.show()
    win.show_library()
    return win


class Ticks:
    """Counts a 5 ms timer's firings: they stop while the GUI thread is blocked."""

    def __init__(self) -> None:
        self.count = 0
        self.timer = QTimer()
        self.timer.setInterval(5)
        self.timer.timeout.connect(self._tick)

    def _tick(self) -> None:
        self.count += 1


def record_threads(monkeypatch: pytest.MonkeyPatch, name: str) -> list[str]:
    """Wrap ``picture_preview.<name>`` to note the thread each call runs on."""
    threads: list[str] = []
    real: Callable[..., Any] = getattr(picture_preview, name)

    def wrapped(*args: Any) -> Any:
        threads.append(threading.current_thread().name)
        return real(*args)

    monkeypatch.setattr(picture_preview, name, wrapped)
    return threads


# ---------------------------------------------------------------- never blocking
@pytest.mark.parametrize(
    ("rel", "job"), [("Big/photo.jpg", "decode_image"), ("Big/booklet.pdf", "read_file")]
)
def test_a_big_file_never_blocks_the_gui_thread(
    window: MainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, rel: str, job: str
) -> None:
    threads = record_threads(monkeypatch, job)
    picture = window.library_page.preview.picture
    ticks = Ticks()
    ticks.timer.start()
    window.library_page.show_resource(rel)
    # Selecting returned at once, with the quiet loading state up...
    assert picture.busy()
    assert window.library_page.preview.content.currentWidget() is picture
    assert picture.view.empty.text() == LOADING
    assert ticks.count == 0
    # ...and the event loop kept turning while the picture loaded elsewhere.
    qtbot.waitUntil(lambda: not picture.busy(), timeout=LOAD_TIMEOUT)
    ticks.timer.stop()
    assert ticks.count > 0
    assert threads and threading.main_thread().name not in threads
    shown = picture.view.picture()
    assert shown is not None and not shown.isNull()


def test_the_photo_is_decoded_at_the_size_it_is_shown(window: MainWindow, qtbot: QtBot) -> None:
    picture = window.library_page.preview.picture
    window.library_page.show_resource("Big/photo.jpg")
    qtbot.waitUntil(lambda: not picture.busy(), timeout=LOAD_TIMEOUT)
    shown = picture.view.picture()
    assert shown is not None
    ratio = picture.devicePixelRatioF()
    # No bigger than the window it is shown in, not the photo's 4032 x 3024.
    assert shown.width() <= window.width() * ratio and shown.height() <= window.height() * ratio
    assert abs(shown.width() / shown.height() - 4032 / 3024) < 0.01


def test_arrowing_through_ten_photos_decodes_one_at_a_time_and_shows_the_last(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = [
        noise_photo(tmp_path / f"photo{i}.jpg", 1600 + 40 * i, 1200, seed=i) for i in range(10)
    ]
    lock = threading.Lock()
    state = {"running": 0, "most": 0}
    decoded: list[Path] = []
    real = picture_preview.decode_image

    def counting(path: Path, bound: QSize) -> QImage:
        with lock:
            state["running"] += 1
            state["most"] = max(state["most"], state["running"])
            decoded.append(path)
        try:
            return real(path, bound)
        finally:
            with lock:
                state["running"] -= 1

    monkeypatch.setattr(picture_preview, "decode_image", counting)
    preview = PicturePreview()
    qtbot.addWidget(preview)
    preview.resize(800, 600)
    preview.show()
    shown: list[Path] = []
    preview.shown.connect(lambda: shown.append(preview.want.path if preview.want else Path()))
    for path in files:  # the arrow key held down: a new row before anything finished
        preview.show_image(path, path.stat().st_mtime)
    qtbot.waitUntil(lambda: not preview.busy() and not preview.working(), timeout=LOAD_TIMEOUT)
    assert state["most"] == 1  # never two decodes at once
    assert decoded == [files[0], files[-1]]  # the one in flight, then only the newest
    assert shown == [files[-1]]  # nothing stale ever reached the screen
    image = preview.view.picture()
    assert image is not None
    assert abs(image.width() / image.height() - (1600 + 40 * 9) / 1200) < 0.01
    assert preview.wait_for_workers()


def test_going_back_to_a_file_is_instant(qtbot: QtBot, tmp_path: Path) -> None:
    first = noise_photo(tmp_path / "a.jpg", 1200, 900, seed=1)
    second = noise_photo(tmp_path / "b.png", 900, 1200, seed=2)
    preview = PicturePreview()
    qtbot.addWidget(preview)
    preview.resize(640, 480)
    preview.show()
    for path in (first, second):
        preview.show_image(path, path.stat().st_mtime)
        qtbot.waitUntil(lambda: not preview.busy(), timeout=LOAD_TIMEOUT)
    preview.show_image(first, first.stat().st_mtime)
    assert not preview.busy() and not preview.working()  # from the cache, no job
    image = preview.view.picture()
    assert image is not None and image.width() > image.height()


def test_a_file_that_is_not_a_picture_says_so(qtbot: QtBot, tmp_path: Path) -> None:
    broken = tmp_path / "broken.png"
    broken.write_bytes(b"not a png at all")
    preview = PicturePreview()
    qtbot.addWidget(preview)
    preview.show_image(broken, broken.stat().st_mtime)
    qtbot.waitUntil(lambda: not preview.busy(), timeout=LOAD_TIMEOUT)
    assert preview.view.picture() is None
    assert "Could not show broken.png" in preview.view.empty.text()
    not_pdf = tmp_path / "fake.pdf"
    not_pdf.write_bytes(b"%PDF-nonsense")
    preview.show_pdf(not_pdf, not_pdf.stat().st_mtime)
    qtbot.waitUntil(lambda: not preview.busy(), timeout=LOAD_TIMEOUT)
    assert "Could not show fake.pdf" in preview.view.empty.text()
    assert not preview.pager.isVisibleTo(preview)


# ---------------------------------------------------------------- orientation and resizing
def test_a_phone_photo_keeps_its_orientation(qtbot: QtBot, tmp_path: Path) -> None:
    """Stored landscape with EXIF orientation 6 (rotate 90° clockwise), as a
    phone held upright saves it: shown portrait, the stored left edge on top."""
    stored = Image.new("RGB", (400, 200), (220, 0, 0))
    stored.paste((0, 0, 220), (0, 0, 200, 200))  # left half blue
    exif = Image.Exif()
    exif[0x0112] = 6
    path = tmp_path / "upright.jpg"
    stored.save(path, exif=exif.tobytes())
    preview = PicturePreview()
    qtbot.addWidget(preview)
    preview.show_image(path, path.stat().st_mtime)
    qtbot.waitUntil(lambda: not preview.busy(), timeout=LOAD_TIMEOUT)
    image = preview.view.picture()
    assert image is not None
    assert (image.width(), image.height()) == (200, 400)
    assert image.pixelColor(100, 20).blue() > 150  # top: what was the left
    assert image.pixelColor(100, 380).red() > 150


def test_resizing_rescales_fast_then_smooth(qtbot: QtBot, tmp_path: Path) -> None:
    path = noise_photo(tmp_path / "wide.jpg", 1600, 1200)
    view = ImageViewWidget()
    qtbot.addWidget(view)
    view.resize(400, 300)
    view.show()
    view.set_picture(QImage(str(path)))
    with qtbot.waitSignal(view.settled, timeout=5000):
        view.resize(800, 600)
        pixmap = view.pixmap()  # rescaled at once (fast), smooth once settled
        assert pixmap is not None and not pixmap.isNull()
    ratio = view.devicePixelRatioF()
    pixmap = view.pixmap()
    assert pixmap is not None
    assert pixmap.width() == round(800 * ratio)  # drawn at device pixels: crisp on Retina


# ---------------------------------------------------------------- PDFs
def test_a_scanned_pdf_shows_its_page_with_a_count_and_steps(qtbot: QtBot, tmp_path: Path) -> None:
    path = scanned_pdf(tmp_path / "scan.pdf", 3)
    preview = PicturePreview()
    qtbot.addWidget(preview)
    preview.resize(600, 700)
    preview.show()
    preview.show_pdf(path, path.stat().st_mtime)
    assert preview.pager.isVisibleTo(preview)
    qtbot.waitUntil(lambda: not preview.busy(), timeout=LOAD_TIMEOUT)

    def middle() -> Any:
        image = preview.view.picture()
        assert image is not None and not image.isNull()
        return image.pixelColor(image.width() // 2, image.height() // 2)

    assert preview.page_label.text() == "Page 1 of 3"
    assert middle().red() > 150  # the page itself, not "no text layer"
    assert not preview.prev_button.isEnabled() and preview.next_button.isEnabled()
    preview.next_button.click()
    assert preview.page_label.text() == "Page 2 of 3"
    qtbot.waitUntil(lambda: not preview.busy(), timeout=LOAD_TIMEOUT)
    assert middle().blue() > 150
    preview.step(5)  # past the end: the last page
    qtbot.waitUntil(lambda: not preview.busy(), timeout=LOAD_TIMEOUT)
    assert preview.page_label.text() == "Page 3 of 3"
    assert not preview.next_button.isEnabled() and preview.prev_button.isEnabled()
    preview.prev_button.click()
    preview.prev_button.click()
    assert preview.page_label.text() == "Page 1 of 3"
    qtbot.waitUntil(lambda: not preview.busy(), timeout=LOAD_TIMEOUT)
    assert middle().red() > 150


def test_the_library_shows_a_pdf_page_not_its_text(window: MainWindow, qtbot: QtBot) -> None:
    preview = window.library_page.preview
    window.library_page.show_resource("Big/booklet.pdf")
    qtbot.waitUntil(lambda: not preview.picture.busy(), timeout=LOAD_TIMEOUT)
    assert preview.content.currentWidget() is preview.picture
    assert preview.picture.page_label.text() == "Page 1 of 40"
    # A Python file next: the picture is put away, so nothing late can show.
    window.library_page.show_resource("Python/Python_Course/while_loops.py")
    assert preview.content.currentWidget() is preview.code
    assert preview.picture.want is None and not preview.picture.busy()
