"""A file as a picture, drawn without ever blocking the window (#64): a photo
decoded at the size it is shown, or a PDF's pages one at a time with
*Page 1 of N* and a way to step through them.

Where the work happens:

* **Images** are decoded by :func:`decode_image` in a :class:`PictureWorker`
  (a :class:`~staffroom.shell.worker.GuiWorker`, #39): ``QImageReader`` with
  a scaled size, so a 12-megapixel phone photo is decoded at the size of the
  preview, the right way up (``setAutoTransform``).
* **PDFs** are read into memory by a :class:`PictureWorker` (plain bytes),
  opened on the GUI thread with :func:`~staffroom.shell.widgets.page_preview.open_pdf`
  (the page preview's loader; opening is quick, drawing is not) and each page
  is drawn by ``QPdfPageRenderer`` in its own thread, as the page preview's
  thumbnails are.

Only plain ``QImage`` results and bytes come back to the GUI thread; every
Qt object this widget keeps is made and dropped there.

One job at a time: a newer request does not start while one is in flight; it
waits, and when the job finishes only the newest request runs next. Arrowing
through ten photos therefore decodes the first and the last, and a result
for anything but the newest request goes to the cache, never on screen.

The last :data:`CACHE_SIZE` pictures are kept by path, modified time and page,
so going back to a file is instant. While a picture is on its way the view
shows a quiet *Loading…*.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QBuffer, QObject, QSize, QSizeF, Qt, Signal
from PySide6.QtGui import QImage, QImageIOHandler, QImageReader
from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions, QPdfPageRenderer
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from staffroom.core.log import get_logger
from staffroom.shell.widgets.card import make_label
from staffroom.shell.widgets.image_view import ImageViewWidget
from staffroom.shell.widgets.page_preview import open_pdf
from staffroom.shell.worker import GuiWorker

log = get_logger(__name__)

CACHE_SIZE = 8  # pictures kept, newest last
LOADING = "Loading…"
MIN_BOUND = QSize(480, 360)  # logical px: never decode smaller than this
SHARPER = 1.25  # a settled view this much bigger than its picture draws it again

Key = tuple[str, float, int]  # path, modified time, page (0 for an image)


def decode_image(path: Path, bound: QSize) -> QImage:
    """The image at ``path`` decoded no larger than ``bound`` (device pixels,
    keeping its aspect), turned the right way up as its EXIF orientation
    says. A null image when it cannot be read. Safe on any thread."""
    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    size = reader.size()  # as stored, before the orientation is applied
    if size.isValid() and bound.isValid():
        if reader.transformation() & QImageIOHandler.Transformation.TransformationRotate90:
            bound = bound.transposed()
        if size.width() > bound.width() or size.height() > bound.height():
            reader.setScaledSize(size.scaled(bound, Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    if image.isNull():
        log.warning("could not decode %s for the preview: %s", path, reader.errorString())
    return image


def read_file(path: Path) -> bytes | str:
    """The file's bytes, or why they could not be read."""
    try:
        return path.read_bytes()
    except OSError as exc:
        log.warning("could not read %s for the preview: %s", path, exc)
        return exc.strerror or str(exc)


class PictureWorker(GuiWorker):
    """Runs ``job`` off the GUI thread and emits what it returned. A job
    returns a value (an image, bytes, a reason); it never raises."""

    done = Signal(object)

    def __init__(self, job: Callable[[], object]) -> None:
        super().__init__()
        self.job = job

    def run(self) -> None:
        self.done.emit(self.job())


class _Keeper(QObject):
    """Holds each worker until its thread has finished, on the GUI thread, so
    a closed preview never drops a ``QThread`` that is still running."""

    def __init__(self) -> None:
        super().__init__()
        self.alive: set[PictureWorker] = set()

    def hold(self, worker: PictureWorker) -> None:
        self.alive.add(worker)
        worker.finished.connect(self.release, Qt.ConnectionType.QueuedConnection)

    def release(self) -> None:
        for worker in [w for w in self.alive if w.isFinished()]:
            worker.wait()
            self.alive.discard(worker)


_keeper: _Keeper | None = None


def keeper() -> _Keeper:
    global _keeper
    if _keeper is None:
        _keeper = _Keeper()
    return _keeper


@dataclass(frozen=True)
class Want:
    """What the view should show: a file at a modified time, and a page."""

    path: Path
    mtime: float
    kind: str  # "image" or "pdf"
    page: int = 0

    @property
    def key(self) -> Key:
        return (str(self.path), self.mtime, self.page)

    @property
    def file(self) -> tuple[str, float]:
        return (str(self.path), self.mtime)


@dataclass
class Picture:
    image: QImage
    pages: int  # 0 for an image
    limited: bool  # drawn smaller than the source could give: a bigger view may redraw it


@dataclass
class _Pdf:
    file: tuple[str, float]
    document: QPdfDocument
    buffer: QBuffer
    renderer: QPdfPageRenderer

    def close(self) -> None:
        self.renderer.pageRendered.disconnect()
        self.renderer.setDocument(None)  # type: ignore[arg-type]
        self.renderer.deleteLater()
        self.document.close()
        self.buffer.close()


class PicturePreview(QWidget):
    """See the module docstring. :meth:`show_image` and :meth:`show_pdf` ask
    for a picture; :meth:`busy` says whether it is still on its way."""

    shown = Signal()  # the wanted picture (or why there is none) is on screen

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PicturePreview")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.view = ImageViewWidget()
        self.view.settled.connect(self._sharpen)
        layout.addWidget(self.view, 1)

        # -- the page bar, for PDFs: Previous, "Page 1 of 60", Next
        self.pager = QWidget()
        bar = QHBoxLayout(self.pager)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(8)
        self.prev_button = QPushButton("‹ Previous")
        self.prev_button.setProperty("role", "ghost")
        self.prev_button.setToolTip("The page before")
        self.prev_button.clicked.connect(lambda: self.step(-1))
        self.page_label = make_label("", "muted")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.next_button = QPushButton("Next ›")
        self.next_button.setProperty("role", "ghost")
        self.next_button.setToolTip("The next page")
        self.next_button.clicked.connect(lambda: self.step(1))
        bar.addStretch(1)
        bar.addWidget(self.prev_button)
        bar.addWidget(self.page_label)
        bar.addWidget(self.next_button)
        bar.addStretch(1)
        self.pager.hide()
        layout.addWidget(self.pager)

        self.want: Want | None = None
        self.on_screen = False
        self.pages = 0  # of the PDF wanted, once known
        self.cache: OrderedDict[Key, Picture] = OrderedDict()
        self.failed: dict[tuple[str, float], str] = {}  # file -> why it shows no picture
        self.worker: PictureWorker | None = None
        self._job_want: Want | None = None
        self._job_bound = QSize()
        self._render: tuple[int, Want, QSize] | None = None  # request id, for, at
        self._pdf: _Pdf | None = None

    # -- asking ----------------------------------------------------------
    def show_image(self, path: Path, mtime: float) -> None:
        self._ask(Want(path, mtime, "image"))

    def show_pdf(self, path: Path, mtime: float, page: int = 0) -> None:
        self._ask(Want(path, mtime, "pdf", page))

    def step(self, delta: int) -> None:
        """Show the page ``delta`` away from this one (PDFs only)."""
        want = self.want
        if want is None or want.kind != "pdf" or not self.pages:
            return
        page = max(0, min(want.page + delta, self.pages - 1))
        if page != want.page:
            self.show_pdf(want.path, want.mtime, page)

    def clear(self) -> None:
        """Show nothing (and forget what was wanted; a job in flight finishes
        into the cache)."""
        self.want = None
        self.on_screen = False
        self.pager.hide()
        self.view.show_message("")

    def busy(self) -> bool:
        """The wanted picture is not on screen yet."""
        return self.want is not None and not self.on_screen

    def working(self) -> bool:
        """A decode, read or page drawing is in flight."""
        return self.worker is not None or self._render is not None

    def wait_for_workers(self, timeout_ms: int = 10_000) -> bool:
        """Wait for a decode or read still running (before the window goes)."""
        worker = self.worker
        if worker is None or not worker.isRunning():
            return True
        return worker.wait(timeout_ms)

    def _ask(self, want: Want) -> None:
        if want.file != (self.want.file if self.want else None):
            self.pages = 0
        self.want = want
        self.on_screen = False
        self._update_pager()
        if not self._display():
            self.view.show_message(LOADING)
            self._pump()

    # -- showing ---------------------------------------------------------
    def _display(self) -> bool:
        """Put the wanted picture on screen if it is to hand."""
        want = self.want
        if want is None:
            return False
        reason = self.failed.get(want.file)
        picture = self.cache.get(want.key)
        if picture is None and reason is None:
            return False
        if picture is not None:
            self.cache.move_to_end(want.key)
            if picture.pages:
                self.pages = picture.pages
            self.view.set_picture(picture.image)
        else:
            self.view.show_message(f"Could not show {want.path.name}: {reason}")
        self.on_screen = True
        self._update_pager()
        self.shown.emit()
        return True

    def _update_pager(self) -> None:
        want = self.want
        is_pdf = want is not None and want.kind == "pdf" and want.file not in self.failed
        self.pager.setVisible(is_pdf)
        if not is_pdf or want is None:
            return
        count = self.pages
        self.page_label.setText(
            f"Page {want.page + 1} of {count}" if count else f"Page {want.page + 1}"
        )
        self.prev_button.setEnabled(want.page > 0)
        self.next_button.setEnabled(want.page + 1 < count)

    def _remember(self, key: Key, picture: Picture) -> None:
        self.cache[key] = picture
        self.cache.move_to_end(key)
        while len(self.cache) > CACHE_SIZE:
            self.cache.popitem(last=False)

    def _bound(self) -> QSize:
        """How big to draw: the view's size (never less than :data:`MIN_BOUND`)
        in device pixels."""
        ratio = self.view.devicePixelRatioF()
        width = max(self.view.width(), MIN_BOUND.width())
        height = max(self.view.height(), MIN_BOUND.height())
        return QSize(round(width * ratio), round(height * ratio))

    def _sharpen(self) -> None:
        """After a resize: draw the picture again if the view has grown well
        past the size it was drawn at."""
        want = self.want
        if want is None or not self.on_screen or self.working():
            return
        picture = self.cache.get(want.key)
        if picture is None or not picture.limited:
            return
        fitted = picture.image.size().scaled(
            self.view.target_size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        if fitted.width() > picture.image.width() * SHARPER:
            del self.cache[want.key]
            self.on_screen = False  # the old picture stays up until the new one comes
            self._pump()

    # -- the one job in flight ----------------------------------------------
    def _pump(self) -> None:
        """Start the job for the wanted picture, unless one is in flight."""
        want = self.want
        if self.working() or want is None or self.on_screen:
            return
        if want.key in self.cache or want.file in self.failed:
            self._display()
            return
        bound = self._bound()
        if want.kind == "image":
            path = want.path
            self._start(want, bound, lambda: decode_image(path, bound))
        elif self._pdf is not None and self._pdf.file == want.file:
            self._request_page(want, bound)
        else:
            path = want.path
            self._start(want, bound, lambda: read_file(path))

    def _start(self, want: Want, bound: QSize, job: Callable[[], object]) -> None:
        worker = PictureWorker(job)
        worker.done.connect(self._job_done, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(self._job_finished, Qt.ConnectionType.QueuedConnection)
        keeper().hold(worker)
        self.worker = worker
        self._job_want = want
        self._job_bound = bound
        worker.start()

    def _job_done(self, result: object) -> None:
        want, bound = self._job_want, self._job_bound
        if want is None:
            return
        if want.kind == "image":
            if isinstance(result, QImage) and not result.isNull():
                limited = (
                    result.width() >= bound.width() - 1 or result.height() >= bound.height() - 1
                )
                self._remember(want.key, Picture(result, 0, limited))
            else:
                self.failed[want.file] = "it is not an image Staffroom can read"
        elif self.want is not None and self.want.file == want.file:
            self._open(want, result)
        # else: bytes of a PDF nobody wants any more; let them go
        if self.want == want and not self.on_screen:
            self._display()

    def _job_finished(self) -> None:
        worker, self.worker = self.worker, None
        self._job_want = None
        if worker is not None:
            worker.wait()
        self._pump()

    # -- PDFs --------------------------------------------------------------
    def _open(self, want: Want, data: object) -> None:
        if self._pdf is not None:
            self._pdf.close()
            self._pdf = None
        opened = open_pdf(data, want.path) if isinstance(data, bytes) else None
        if opened is None:
            reason = data if isinstance(data, str) else "it is not a PDF Staffroom can open"
            self.failed[want.file] = reason
            return
        document, buffer = opened
        renderer = QPdfPageRenderer(self)
        renderer.setRenderMode(QPdfPageRenderer.RenderMode.MultiThreaded)
        renderer.setDocument(document)
        renderer.pageRendered.connect(self._page_rendered)
        self._pdf = _Pdf(want.file, document, buffer, renderer)
        self.pages = document.pageCount()
        self._update_pager()

    def _request_page(self, want: Want, bound: QSize) -> None:
        assert self._pdf is not None
        document = self._pdf.document
        page = max(0, min(want.page, document.pageCount() - 1))
        points = document.pagePointSize(page)
        if points.isEmpty():
            points = QSizeF(595.0, 842.0)
        size = points.scaled(QSizeF(bound), Qt.AspectRatioMode.KeepAspectRatio).toSize()
        size = QSize(max(1, size.width()), max(1, size.height()))
        rid = self._pdf.renderer.requestPage(page, size, QPdfDocumentRenderOptions())
        self._render = (int(rid), want, size)

    def _page_rendered(
        self, _page: int, _size: QSize, image: QImage, _options: object, rid: int
    ) -> None:
        if self._render is None or int(rid) != self._render[0] or self._pdf is None:
            return
        _rid, want, _at = self._render
        self._render = None
        if image.isNull():
            self.failed[want.file] = "its page could not be drawn"
        else:
            pages = self._pdf.document.pageCount()
            self._remember(want.key, Picture(image, pages, True))
        if self.want == want and not self.on_screen:
            self._display()
        self._pump()
