"""The pages a run wrote, as they will print (:class:`~staffroom.core.panel.PagePreview`).

The PDF itself, drawn by Qt's own PDF module (``PySide6.QtPdf``, part of
PySide6): the current page large, fitted whole into the space; down the right
a rail of thumbnails, every page of the sheet and then of the key ("Sheet ·
page 1", "Key · page 1"); under the rail *Open PDF* (the file in its own app)
and *Print…* (the system print dialog, then the pages as they look here).

Two parts, ``"sheet"`` and ``"key"``. The output pane shows them as two tabs
and tells this widget which one is current (:meth:`show_part`); a click on a
thumbnail of the other part asks the pane to switch tabs
(:attr:`part_requested`).

Long sheets stay quick: the files are read into memory once (a rerun that
overwrites them never pulls a page from under the view), the large page is
rendered by :class:`QPdfView` in its own thread, and a thumbnail is rendered,
off the GUI thread, only when its row first scrolls into view.

With no PDF (the teacher asked for Word only) the rail goes and a note says
why, over the plain text of the part, so the tab is never empty.

Colours come from the stylesheet (``qproperty-*`` on ``PageCanvas`` and
``PageRail`` in ``shell/theme.py``), never from this file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QBuffer,
    QByteArray,
    QIODevice,
    QMargins,
    QModelIndex,
    QPersistentModelIndex,
    QPointF,
    QRect,
    QRectF,
    QSize,
    QSizeF,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPalette, QPen, QPixmap
from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions, QPdfPageRenderer
from PySide6.QtPdfWidgets import QPdfView
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QLabel,
    QListView,
    QPlainTextEdit,
    QPushButton,
    QStackedLayout,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.log import get_logger
from staffroom.core.panel import Pages
from staffroom.shell.widgets.paint import color_property, default_colors

log = get_logger(__name__)

PARTS = ("sheet", "key")
PART_NAMES = {"sheet": "Sheet", "key": "Key"}
THUMB_WIDTH = 112  # logical px of a thumbnail page
THUMB_CAPTION = 22  # the caption line under it
THUMB_PAD = 8  # around the page inside its row (room for the selection ring)
RAIL_WIDTH = THUMB_WIDTH + 2 * THUMB_PAD + 26  # the list's frame and scrollbar
A4_RATIO = 297 / 210
PRINT_DPI = 300  # pages are drawn for the printer at this resolution at most
PAGE_MARGIN = 16  # around the large page

Ref = tuple[str, int]  # (part, page index)


def page_label(part: str, page: int) -> str:
    """``"Sheet · page 1"``: a thumbnail's caption (``page`` counts from 0)."""
    return f"{PART_NAMES.get(part, part.title())} · page {page + 1}"


def pages_phrase(count: int) -> str:
    return f"{count} page{'s' if count != 1 else ''}"


def load_pdf(path: Path) -> tuple[QPdfDocument, QBuffer] | None:
    """The PDF at ``path`` read into memory, or None when it cannot be read.
    The buffer must live as long as the document."""
    try:
        data = path.read_bytes()
    except OSError as exc:
        log.warning("could not read %s for the page preview: %s", path, exc)
        return None
    buffer = QBuffer()
    buffer.setData(QByteArray(data))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    document = QPdfDocument()
    document.load(buffer)
    if document.status() != QPdfDocument.Status.Ready or document.pageCount() < 1:
        log.warning("could not open %s for the page preview: %s", path, document.error())
        return None
    return document, buffer


def print_pdf(document: QPdfDocument, printer: object, first: int = 0, last: int = -1) -> int:
    """Draw pages ``first``..``last`` (0-based, inclusive; -1: to the end) of
    ``document`` on ``printer`` (a ``QPrinter``), each fitted to the paper at
    up to :data:`PRINT_DPI`. Returns the number of pages drawn."""
    from PySide6.QtPrintSupport import QPrinter

    assert isinstance(printer, QPrinter)
    count = document.pageCount()
    last = count - 1 if last < 0 else min(last, count - 1)
    painter = QPainter()
    if count == 0 or first > last or not painter.begin(printer):
        return 0
    drawn = 0
    try:
        for index in range(first, last + 1):
            if drawn:
                printer.newPage()
            target = QRectF(painter.viewport())
            points = document.pagePointSize(index)
            if points.isEmpty():
                points = QSizeF(595.0, 842.0)
            scale = min(target.width() / points.width(), target.height() / points.height())
            size = QSizeF(points.width() * scale, points.height() * scale)
            box = QRectF(
                target.x() + (target.width() - size.width()) / 2,
                target.y() + (target.height() - size.height()) / 2,
                size.width(),
                size.height(),
            )
            cap = PRINT_DPI / 72
            pixels = QSize(
                max(1, round(min(size.width(), points.width() * cap))),
                max(1, round(min(size.height(), points.height() * cap))),
            )
            painter.drawImage(box, document.render(index, pixels))
            drawn += 1
    finally:
        painter.end()
    return drawn


@dataclass
class _Part:
    path: Path
    document: QPdfDocument
    buffer: QBuffer
    renderer: QPdfPageRenderer


class ThumbModel(QAbstractListModel):
    """One row per page, sheet then key. A row's picture is rendered the
    first time a view asks for it (that is, when it is painted), in the PDF
    renderer's own thread; until it arrives the delegate draws a blank page."""

    RefRole = Qt.ItemDataRole.UserRole + 1
    SizeRole = Qt.ItemDataRole.UserRole + 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.parts: dict[str, _Part] = {}
        self.rows: list[Ref] = []
        self.images: dict[Ref, QPixmap] = {}
        self.requests: dict[tuple[str, int], Ref] = {}  # (part, request id) -> page
        self.requested: set[Ref] = set()
        self.ratio = 2.0

    def set_parts(self, parts: dict[str, _Part], ratio: float) -> None:
        self.beginResetModel()
        for part in self.parts.values():
            part.renderer.pageRendered.disconnect()
        self.parts = parts
        self.ratio = max(ratio, 1.0)
        self.rows = [
            (p, i) for p in PARTS if p in parts for i in range(parts[p].document.pageCount())
        ]
        self.images = {}
        self.requests = {}
        self.requested = set()
        for name, part in parts.items():
            part.renderer.pageRendered.connect(
                lambda page, _size, image, _opts, rid, n=name: self._rendered(n, page, image, rid)
            )
        self.endResetModel()

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex | None = None) -> int:  # noqa: N802
        if parent is not None and parent.isValid():
            return 0
        return len(self.rows)

    def row_of(self, ref: Ref) -> int:
        try:
            return self.rows.index(ref)
        except ValueError:
            return -1

    def thumb_size(self, ref: Ref) -> QSize:
        part = self.parts.get(ref[0])
        points = part.document.pagePointSize(ref[1]) if part else QSizeF()
        ratio = points.height() / points.width() if points.width() > 0 else A4_RATIO
        return QSize(THUMB_WIDTH, max(1, round(THUMB_WIDTH * ratio)))

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        ref = self.rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return page_label(*ref)
        if role == Qt.ItemDataRole.ToolTipRole:
            part = self.parts.get(ref[0])
            return f"{page_label(*ref)} of {part.path.name}" if part else None
        if role == self.RefRole:
            return ref
        if role == self.SizeRole:
            return self.thumb_size(ref)
        if role == Qt.ItemDataRole.DecorationRole:
            image = self.images.get(ref)
            if image is None:
                self.request(ref)
            return image
        return None

    def request(self, ref: Ref) -> None:
        """Ask for ``ref``'s picture once; it arrives through ``_rendered``."""
        if ref in self.requested or ref[0] not in self.parts:
            return
        self.requested.add(ref)
        size = self.thumb_size(ref)
        pixels = QSize(round(size.width() * self.ratio), round(size.height() * self.ratio))
        renderer = self.parts[ref[0]].renderer
        rid = renderer.requestPage(ref[1], pixels, QPdfDocumentRenderOptions())
        self.requests[(ref[0], int(rid))] = ref

    def pending(self) -> int:
        """Thumbnails asked for and not yet drawn."""
        return len(self.requested) - len(self.images)

    def _rendered(self, part: str, page: int, image: QImage, rid: int) -> None:
        ref = self.requests.pop((part, int(rid)), (part, page))
        if ref[0] not in self.parts:
            return
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(self.ratio)
        self.images[ref] = pixmap
        row = self.row_of(ref)
        if row >= 0:
            index = self.index(row)
            self.dataChanged.emit(index, index, [Qt.ItemDataRole.DecorationRole])


class ThumbDelegate(QStyledItemDelegate):
    """A thumbnail: the page on paper with a hairline edge (a ring in the
    accent when it is the page shown large), its caption underneath."""

    def __init__(self, rail: PageRail) -> None:
        super().__init__(rail)
        self.rail = rail

    def sizeHint(  # noqa: N802
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        size = index.data(ThumbModel.SizeRole)
        height = size.height() if isinstance(size, QSize) else round(THUMB_WIDTH * A4_RATIO)
        return QSize(THUMB_WIDTH + 2 * THUMB_PAD, height + 2 * THUMB_PAD + THUMB_CAPTION)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        colors = self.rail.colors
        size = index.data(ThumbModel.SizeRole)
        if not isinstance(size, QSize):
            size = QSize(THUMB_WIDTH, round(THUMB_WIDTH * A4_RATIO))
        rect: QRect = option.rect
        x = rect.x() + (rect.width() - size.width()) // 2
        page = QRect(x, rect.y() + THUMB_PAD, size.width(), size.height())
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(page, colors["paper"])
        pixmap = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            painter.drawPixmap(page, pixmap)
        if selected:
            painter.setPen(QPen(colors["accent"], 2))
            painter.drawRect(page.adjusted(-3, -3, 3, 3))
        else:
            painter.setPen(QPen(colors["edge"], 1))
            painter.drawRect(page.adjusted(0, 0, -1, -1))
        painter.setPen(colors["text"] if selected else colors["caption"])
        font = painter.font()
        font.setPixelSize(12)
        painter.setFont(font)
        caption = QRect(page.x(), page.bottom() + 5, page.width(), THUMB_CAPTION - 4)
        flags = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        painter.drawText(caption, int(flags), str(index.data(Qt.ItemDataRole.DisplayRole) or ""))
        painter.restore()


class PageRail(QListView):
    """The thumbnails, one column, sheet pages then key pages."""

    def __init__(self, model: ThumbModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageRail")
        self.setProperty("ring", "current")  # the accent rings the current page (theme.py)
        self._colors = default_colors("paper", "edge", "accent", "text", "caption")
        self.setModel(model)
        self.setItemDelegate(ThumbDelegate(self))
        self.setUniformItemSizes(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedWidth(RAIL_WIDTH)
        self.setSpacing(2)

    @property
    def colors(self) -> dict[str, QColor]:
        return self._colors

    paperColor = color_property("paper")  # noqa: N815
    edgeColor = color_property("edge")  # noqa: N815
    accentColor = color_property("accent")  # noqa: N815
    textColor = color_property("text")  # noqa: N815
    captionColor = color_property("caption")  # noqa: N815


class PageCanvas(QPdfView):
    """The current page, whole, on the canvas colour (``qproperty-canvasColor``)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]  # Qt takes no parent too
        self.setObjectName("PageCanvas")
        self._colors = default_colors("canvas")
        self.setPageMode(QPdfView.PageMode.SinglePage)
        self.setZoomMode(QPdfView.ZoomMode.FitInView)
        self.setDocumentMargins(QMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN))
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMinimumSize(240, 300)

    def _get_canvas(self) -> QColor:
        return self._colors["canvas"]

    def _set_canvas(self, color: QColor) -> None:
        # QPdfView paints its background with the palette's Dark role.
        self._colors["canvas"] = QColor(color)
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Dark, QColor(color))
        self.setPalette(palette)
        self.viewport().update()

    canvasColor = Property(QColor, _get_canvas, _set_canvas)  # noqa: N815


class PagePreviewWidget(QWidget):
    """See the module docstring. :meth:`set_pages` after a run, :meth:`show_part`
    when the pane's tab changes, :meth:`clear` before the next run."""

    part_requested = Signal(str)  # a thumbnail of the other part was clicked
    open_requested = Signal(object)  # Path: Open PDF
    page_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PagePreview")
        self.pages: Pages | None = None
        self.parts: dict[str, _Part] = {}
        self.part = "sheet"
        self.page = 0
        self._last_page: dict[str, int] = {}

        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)

        # -- the pages: canvas left, rail and buttons right
        viewer = QWidget()
        row = QHBoxLayout(viewer)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        self.canvas = PageCanvas()
        row.addWidget(self.canvas, 1)
        side = QVBoxLayout()
        side.setContentsMargins(0, 0, 0, 0)
        side.setSpacing(8)
        self.model = ThumbModel(self)
        self.rail = PageRail(self.model)
        self.rail.clicked.connect(self._thumb_clicked)
        self.rail.selectionModel().currentChanged.connect(self._thumb_current)
        side.addWidget(self.rail, 1)
        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        self.open_button = QPushButton("Open PDF")
        self.open_button.clicked.connect(self._open_current)
        self.print_button = QPushButton("Print…")
        self.print_button.clicked.connect(self.print_current)
        buttons.addWidget(self.open_button)
        buttons.addWidget(self.print_button)
        side.addLayout(buttons)
        row.addLayout(side)
        self.stack.addWidget(viewer)

        # -- no PDF: a note over the plain text
        fallback = QWidget()
        col = QVBoxLayout(fallback)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        self.note = QLabel("")
        self.note.setObjectName("PageNote")
        self.note.setWordWrap(True)
        self.note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.note)
        self.text = QPlainTextEdit()
        self.text.setObjectName("CodeView")
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        col.addWidget(self.text, 1)
        self.stack.addWidget(fallback)
        self._viewer, self._fallback = viewer, fallback

    # -- state -----------------------------------------------------------
    def has_pdf(self) -> bool:
        return bool(self.parts)

    def has_part(self, part: str) -> bool:
        """Whether ``part`` has anything to show (pages, or text without a PDF)."""
        if self.pages is None:
            return part == "sheet"
        if self.parts:
            return part in self.parts
        return part == "sheet" or bool(self.pages.key_text)

    def page_count(self, part: str) -> int:
        entry = self.parts.get(part)
        return entry.document.pageCount() if entry else 0

    def path(self, part: str | None = None) -> Path | None:
        entry = self.parts.get(part or self.part)
        return entry.path if entry else None

    def busy(self) -> bool:
        """Thumbnails still being drawn (for screenshots and tests)."""
        return self.model.pending() > 0

    # -- filling ---------------------------------------------------------
    def clear(self) -> None:
        """Drop the documents (before a run rewrites the files)."""
        self.canvas.setDocument(None)  # type: ignore[arg-type]
        self.model.set_parts({}, self.devicePixelRatioF())
        for entry in self.parts.values():
            entry.document.close()
            entry.buffer.close()
        self.parts = {}
        self.pages = None
        self._last_page = {}

    def set_pages(self, pages: Pages) -> None:
        self.clear()
        self.pages = pages
        parts: dict[str, _Part] = {}
        for name, path in (("sheet", pages.sheet), ("key", pages.key)):
            if path is None:
                continue
            loaded = load_pdf(path)
            if loaded is None:
                continue
            document, buffer = loaded
            renderer = QPdfPageRenderer(self)
            renderer.setRenderMode(QPdfPageRenderer.RenderMode.MultiThreaded)
            renderer.setDocument(document)
            parts[name] = _Part(path, document, buffer, renderer)
        self.parts = parts
        self.model.set_parts(parts, self.devicePixelRatioF())
        if parts:
            self.stack.setCurrentWidget(self._viewer)
        else:
            unreadable = pages.has_pdf
            self.note.setText(
                "Could not open the PDF to show its pages. Use the file buttons above to "
                "open it in its own app."
                if unreadable
                else pages.note
            )
            self.stack.setCurrentWidget(self._fallback)
        first = "sheet" if "sheet" in parts or not parts else next(iter(parts))
        self.show_part(first, 0)

    def show_part(self, part: str, page: int | None = None) -> None:
        """Show ``part`` (``"sheet"`` or ``"key"``) at ``page``, or where it
        was last left."""
        if self.part in self.parts:
            self._last_page[self.part] = self.page
        self.part = part
        if not self.parts:
            pages = self.pages
            text = "" if pages is None else (pages.key_text if part == "key" else pages.sheet_text)
            self.text.setPlainText(text)
            self.text.setVisible(bool(text))
            self.page = 0
            self.page_changed.emit()
            return
        entry = self.parts.get(part)
        if entry is None:
            return
        count = entry.document.pageCount()
        wanted = self._last_page.get(part, 0) if page is None else page
        self.page = max(0, min(wanted, count - 1))
        if self.canvas.document() is not entry.document:
            self.canvas.setDocument(entry.document)
        self.canvas.pageNavigator().jump(self.page, QPointF(), 0)
        row = self.model.row_of((part, self.page))
        if row >= 0:
            index = self.model.index(row)
            self.rail.blockSignals(True)
            self.rail.selectionModel().blockSignals(True)
            self.rail.setCurrentIndex(index)
            self.rail.selectionModel().blockSignals(False)
            self.rail.blockSignals(False)
            self.rail.scrollTo(index)
            self.rail.viewport().update()
        tip = entry.path.name
        self.open_button.setToolTip(f"Open {tip} in its own app")
        self.print_button.setToolTip(f"Print {tip}")
        self.page_changed.emit()

    def show_page(self, page: int) -> None:
        self.show_part(self.part, page)

    def _thumb_clicked(self, index: QModelIndex) -> None:
        self._go_to(index)

    def _thumb_current(self, index: QModelIndex, _previous: QModelIndex) -> None:
        self._go_to(index)  # arrow keys in the rail

    def _go_to(self, index: QModelIndex) -> None:
        ref = index.data(ThumbModel.RefRole)
        if not isinstance(ref, tuple):
            return
        part, page = ref
        if part != self.part:
            self._last_page[part] = page
            self.part_requested.emit(part)  # the pane switches tabs, then calls show_part
            if self.part != part:  # nobody listening: switch here
                self.show_part(part, page)
        elif page != self.page:
            self.show_part(part, page)

    # -- actions ---------------------------------------------------------
    def _open_current(self) -> None:
        path = self.path()
        if path is not None:
            self.open_requested.emit(path)

    def print_current(self) -> None:
        """The system print dialog for the part on show, then its pages."""
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter

        entry = self.parts.get(self.part)
        if entry is None:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setFullPage(True)  # the PDF carries its own margins
        printer.setDocName(entry.path.stem)
        count = entry.document.pageCount()
        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle(f"Print {entry.path.name}")
        dialog.setMinMax(1, count)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        first, last = 0, count - 1
        if printer.printRange() == QPrinter.PrintRange.PageRange:
            first, last = printer.fromPage() - 1, printer.toPage() - 1
        elif printer.printRange() == QPrinter.PrintRange.CurrentPage:
            first = last = self.page
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            print_pdf(entry.document, printer, first, last)
        finally:
            QApplication.restoreOverrideCursor()
