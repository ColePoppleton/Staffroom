"""The right-hand side of the workbench: a panel's output widgets, filled from
a RunResult.

Top to bottom:

* ``strip_slot`` holding the :class:`ResultStrip`: how the last run went, the
  files it wrote as buttons, its warnings.
* Headline views (``place="top"``, e.g. :class:`StatTilesWidget`), shown once
  filled.
* The main view: one tab per main output (see :func:`core.panel.main_outputs`).
  A single main output still gets its one tab, so the title sits in the same
  place in every tool. Each tab shows a short hint until its first result.
  A ``PagePreview`` takes two tabs, *Sheet* and *Key* (each with its page
  count), sharing one :class:`PagePreviewWidget` that moves to whichever is
  current; the PDF's file name sits at the tab bar's right. A run with no
  pages for it hides both tabs, and an ``optional`` text view shows its tab
  only while the latest run filled it.
  With ``main_layout="row"`` the main outputs sit side by side instead, each
  in a titled card (a report: chart beside table), stacking when the pane is
  too narrow for them.
* Secondary outputs (ActionTable lists, notes) as sections under the main view;
  a ``collapsed`` table folds under a one-line heading the user opens.
* A ``ResultsTable`` asked to fit the screen (``compact``, ``lift_constants``,
  ``mark_changes``, ``pin_last``) is a :class:`FitTable`; a ``CardList`` is a
  :class:`CardListWidget`.
* The *Details* footer: one line (the toggle and the latest log line) that
  opens the run log above it. Closed by default; open or closed is remembered
  per tool for the session. Every panel has it, whether or not its spec lists
  a ``LogArea``.

The pane scrolls as a whole only when the secondary sections do not fit; the
main view always starts at the top, so a result never lands below the fold.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedLayout,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.panel import (
    ActionTable,
    BarChart,
    CardList,
    ImageView,
    MainLayout,
    OutputWidget,
    PagePreview,
    ResultsTable,
    StatTiles,
    TextView,
    ViewWidget,
    below_outputs,
    main_outputs,
    stats_from_table,
    top_outputs,
)
from staffroom.core.plugin import RunResult
from staffroom.shell.widgets.action_table import ActionTableWidget
from staffroom.shell.widgets.bar_chart import BarChartWidget
from staffroom.shell.widgets.card import make_label
from staffroom.shell.widgets.card_list import CardListWidget
from staffroom.shell.widgets.code_view import CodeViewWidget
from staffroom.shell.widgets.elided_label import ElidedLabel
from staffroom.shell.widgets.fit_table import FitTable
from staffroom.shell.widgets.image_view import ImageViewWidget
from staffroom.shell.widgets.input_group import eyebrow
from staffroom.shell.widgets.page_preview import PagePreviewWidget, pages_phrase
from staffroom.shell.widgets.result_strip import ResultStrip
from staffroom.shell.widgets.stat_tiles import StatTilesWidget
from staffroom.shell.widgets.table_view import TableModel, TableWidget
from staffroom.shell.widgets.text_view import TextViewWidget

MAIN_MIN_HEIGHT = 300  # the main view never shrinks below this; the pane scrolls instead
MAIN_SHARE = 0.6  # ...nor below this share of the visible height
BELOW_TABLE_ROWS = 8
LOG_HEIGHT = 180  # the run log when Details is open
BELOW_TEXT_MIN, BELOW_TEXT_MAX = 72, 240
ROW_TABLE_ROWS = 40  # a report's table shows its rows; the pane scrolls past this
ROW_SPACING = 12
COMPACT_COLUMN = 40  # narrowest column of a hinted (report) table
CARD_PADDING = 10
FOLD_CLOSED, FOLD_OPEN = "▸", "▾"
QWIDGETSIZE_MAX = 16777215
DETAILS_CLOSED, DETAILS_OPEN = "Details ▸", "Details ▾"

# Details open or closed, per tool, for as long as the app runs.
_details_open: dict[str, bool] = {}


def _copy_text(view: QPlainTextEdit) -> None:
    QApplication.clipboard().setText(view.toPlainText())


class ReportCard(QFrame):
    """One main view of a ``"row"`` layout: a heading (title, a short caption,
    room for a switch) over the view."""

    def __init__(self, title: str, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ReportCard")
        self.content = content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(CARD_PADDING, 10, CARD_PADDING, 10)
        layout.setSpacing(8)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.title = make_label(title, "section")
        self.caption = make_label("", "faint")
        self.caption.setVisible(False)
        head.addWidget(self.title)
        head.addStretch(1)
        head.addWidget(self.caption)
        self.trailing = QHBoxLayout()
        self.trailing.setSpacing(4)
        head.addLayout(self.trailing)
        layout.addLayout(head)
        if isinstance(content, TableWidget):  # fitted to its rows; spare height under it
            layout.addWidget(content)
            layout.addStretch(1)
        else:  # a chart fills the card (to its maximum), so cards in a row match
            layout.addWidget(content, 1)
            layout.addStretch(0)

    def set_caption(self, text: str) -> None:
        self.caption.setText(text)
        self.caption.setVisible(bool(text))

    def natural_width(self) -> int:
        """The width the view needs without squeezing: a chart's bars at their
        ease, a table's fitted columns."""
        content = self.content
        if isinstance(content, BarChartWidget):
            inner = content.sizeHint().width()
        elif isinstance(content, TableWidget):
            inner = content.horizontalHeader().length() + content.frameWidth() * 2 + 2
        else:
            inner = 280
        return inner + 2 * CARD_PADDING + 2

    def minimum_width(self) -> int:
        """The narrowest it can go beside another card: a chart squeezes its
        bars, a table does not (it would scroll sideways)."""
        if isinstance(self.content, BarChartWidget):
            return self.content.minimumSizeHint().width() + 2 * CARD_PADDING + 2
        return self.natural_width()

    def grows(self) -> bool:
        """Whether it takes a share of spare width (tables keep their fit)."""
        return not isinstance(self.content, TableWidget)


class MainRow(QWidget):
    """The main views side by side; stacked when the pane is narrower than
    their minimum widths. Tables keep their fitted width; charts and other
    views share what is left."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cards: list[ReportCard] = []
        self.box = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.box.setContentsMargins(0, 0, 0, 0)
        self.box.setSpacing(ROW_SPACING)

    def add(self, card: ReportCard) -> None:
        self.box.addWidget(card, 1 if card.grows() else 0)
        self.cards.append(card)

    def needed_width(self) -> int:
        return sum(c.minimum_width() for c in self.cards) + ROW_SPACING * (len(self.cards) - 1)

    def stacked(self) -> bool:
        return self.box.direction() == QBoxLayout.Direction.TopToBottom

    def relayout(self) -> None:
        stack = self.width() < self.needed_width()
        want = QBoxLayout.Direction.TopToBottom if stack else QBoxLayout.Direction.LeftToRight
        if self.box.direction() != want:
            self.box.setDirection(want)
        for card in self.cards:
            if stack or card.grows():
                card.setMinimumWidth(0 if stack else card.minimum_width())
                card.setMaximumWidth(QWIDGETSIZE_MAX)
            else:
                card.setFixedWidth(card.natural_width())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.relayout()


class OutputPane(QWidget):
    action_requested = Signal(str, object)  # from any ActionTable: name, row dict
    open_requested = Signal(object)  # Path: a page preview's Open PDF

    def __init__(
        self,
        outputs: tuple[OutputWidget, ...],
        parent: QWidget | None = None,
        *,
        empty_text: str = "Results appear here after a run.",
        main_layout: MainLayout = "tabs",
        open_label: str = "Folder",
        details_key: str = "",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("OutputPane")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.details_key = details_key
        self.tables: dict[str, tuple[TableModel, TableWidget, QLabel]] = {}
        self.fit_tables: dict[str, FitTable] = {}  # tables fitted to the screen (by key)
        self.card_lists: dict[str, CardListWidget] = {}
        self.action_tables: dict[str, ActionTableWidget] = {}
        self.text_views: dict[str, TextViewWidget | CodeViewWidget] = {}
        self.images: dict[str, ImageViewWidget] = {}
        self.tiles: dict[str, StatTilesWidget] = {}
        self.charts: dict[str, BarChartWidget] = {}
        self.page_previews: dict[str, PagePreviewWidget] = {}
        self.page_names: dict[str, QLabel] = {}  # per PagePreview: its PDF's name, in the corner
        # Per main tab, in order: the view's key and, for a PagePreview, its part.
        self.tab_refs: list[tuple[str, str | None]] = []
        # PagePreview key -> part -> its tab page's layout, which takes the preview in turn
        self._page_tabs: dict[str, dict[str, QVBoxLayout]] = {}
        self._page_labels: dict[tuple[str, str], str] = {}  # (key, part) -> "Sheet"
        self._optional: set[str] = set()  # optional text views: tab shown only when filled
        self.copy_buttons: dict[str, QPushButton] = {}
        self.corner_buttons: dict[str, QPushButton] = {}  # per main view, shown with its tab
        self.cards: dict[str, ReportCard] = {}
        self.folds: dict[str, QPushButton] = {}  # collapsed below sections: their toggles
        # Each view's container: its tab page or card (main), or its section.
        self.sections: dict[str, QWidget] = {}
        self.empty_text = empty_text
        self.empty_labels: list[QLabel] = []  # each main view's hint before a result
        self.main_layout = main_layout
        self._waiting: dict[str, QStackedLayout] = {}  # main views before their first result
        self._below_hidden: set[str] = set()  # below sections shown once filled
        self._fit_below_text: set[str] = set()  # below text views sized to their text
        self._specs: dict[str, ViewWidget] = {w.key: w for w in top_outputs(outputs)}
        main = main_outputs(outputs)
        self._specs.update({w.key: w for w in [*main, *below_outputs(outputs)]})
        self.main_keys = [w.key for w in main]
        self.top_keys = [w.key for w in top_outputs(outputs)]

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # The pane's top edge: the result strip.
        self.strip_slot = QVBoxLayout()
        self.strip_slot.setContentsMargins(0, 0, 0, 0)
        self.strip = ResultStrip(open_label=open_label)
        self.strip_slot.addWidget(self.strip)
        root.addLayout(self.strip_slot)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("OutputScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("OutputBody")
        self.body_layout = QVBoxLayout(body)
        self.body_layout.setContentsMargins(20, 10, 20, 16)
        self.body_layout.setSpacing(16)
        self.scroll_area.setWidget(body)
        root.addWidget(self.scroll_area, 1)

        for spec in top_outputs(outputs):
            self.body_layout.addWidget(self._top_section(spec))

        self.row: MainRow | None = None
        self._row_stack: QStackedLayout | None = None
        self.tabs: QTabWidget | None = None
        if main_layout == "row" and main:
            self.body_layout.addWidget(self._main_row(main))
        else:
            self._build_tabs(main)

        for spec in below_outputs(outputs):
            self.body_layout.addWidget(self._below_section(spec))
        if not main or main_layout == "row":
            self.body_layout.addStretch(1)

        root.addWidget(self._details(fill=not main), 0 if main else 1)

    def _build_tabs(self, main: list[ViewWidget]) -> None:
        tabs = QTabWidget()
        self.tabs = tabs
        tabs.setObjectName("OutputTabs")
        bar = tabs.tabBar()
        bar.setDrawBase(False)  # the pane's top border is the one hairline
        bar.setExpanding(False)
        bar.setUsesScrollButtons(False)
        bar.setElideMode(Qt.TextElideMode.ElideRight)
        tabs.setMinimumHeight(MAIN_MIN_HEIGHT)
        corner = QWidget()
        corner.setObjectName("TabCorner")
        self._corner = QHBoxLayout(corner)
        self._corner.setContentsMargins(0, 0, 0, 4)
        self._corner.setSpacing(6)
        for spec in main:
            if isinstance(spec, PagePreview):
                self._add_page_tabs(tabs, spec)
                continue
            index = tabs.addTab(self._main_page(spec), spec.label)
            tabs.setTabToolTip(index, spec.label)
            self.tab_refs.append((spec.key, None))
            if isinstance(spec, TextView) and spec.optional:
                self._optional.add(spec.key)
                tabs.setTabVisible(index, False)
        tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        tabs.currentChanged.connect(self._show_corner)
        self._show_corner(tabs.currentIndex())
        self.body_layout.addWidget(tabs, 1)
        tabs.setVisible(bool(main))

    def _add_page_tabs(self, tabs: QTabWidget, spec: PagePreview) -> None:
        """Two tabs, sheet and key, sharing one preview that moves to the
        current one (:meth:`_show_corner`)."""
        preview = PagePreviewWidget()
        self.page_previews[spec.key] = preview
        preview.open_requested.connect(self.open_requested.emit)
        preview.part_requested.connect(lambda part, k=spec.key: self.show_part(k, part))
        preview.page_changed.connect(lambda k=spec.key: self._name_page(k))
        holder = QWidget()
        holder.setObjectName("PageHolder")
        stack = QStackedLayout(holder)
        stack.setContentsMargins(0, 0, 0, 0)
        empty = self._empty_label()
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setWordWrap(True)
        stack.addWidget(empty)
        stack.addWidget(preview)
        self._waiting[spec.key] = stack
        name = QLabel("")
        name.setProperty("role", "faint")
        name.setVisible(False)
        self.page_names[spec.key] = name
        self._corner.addWidget(name)
        pages: dict[str, QVBoxLayout] = {}
        for part, label in (("sheet", spec.sheet_label), ("key", spec.key_label)):
            page = QWidget()
            page.setObjectName("OutputPage")
            layout = QVBoxLayout(page)
            layout.setContentsMargins(0, 12, 0, 0)
            layout.setSpacing(0)
            index = tabs.addTab(page, label)
            tabs.setTabToolTip(index, f"{spec.label}: {label.lower()}")
            self._page_labels[(spec.key, part)] = label
            self.tab_refs.append((spec.key, part))
            pages[part] = layout
        self._page_tabs[spec.key] = pages
        pages["sheet"].addWidget(holder)
        self.sections[spec.key] = holder

    def _tab_index(self, key: str, part: str | None = None) -> int:
        try:
            return self.tab_refs.index((key, part))
        except ValueError:
            return -1

    def show_part(self, key: str, part: str) -> None:
        """Bring a page preview's ``part`` tab to the front."""
        index = self._tab_index(key, part)
        if self.tabs is not None and index >= 0 and self.tabs.isTabVisible(index):
            self.tabs.setCurrentIndex(index)

    def _count_pages(self, key: str) -> None:
        """Each page tab says how many pages it holds ("Sheet · 2 pages")."""
        preview = self.page_previews[key]
        for part in ("sheet", "key"):
            index = self._tab_index(key, part)
            if self.tabs is None or index < 0:
                continue
            label = self._page_labels[(key, part)]
            count = preview.page_count(part)
            self.tabs.setTabText(index, f"{label} · {pages_phrase(count)}" if count else label)

    def _name_page(self, key: str) -> None:
        preview = self.page_previews[key]
        path = preview.path()
        label = self.page_names[key]
        label.setText(path.name if path else "")
        label.setToolTip(str(path) if path else "")

    def _main_row(self, main: list[ViewWidget]) -> QWidget:
        """The ``"row"`` layout: a hint until the first result, then the cards."""
        holder = QWidget()
        holder.setObjectName("MainRowHolder")
        stack = QStackedLayout(holder)
        stack.setContentsMargins(0, 0, 0, 0)
        empty = self._empty_label()
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setWordWrap(True)
        empty.setMinimumHeight(MAIN_MIN_HEIGHT)
        self.row = MainRow()
        for spec in main:
            content, extras = self._content(spec)
            if isinstance(content, TableWidget):  # fitted to its columns: never sideways
                content.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            card = ReportCard(spec.label, content)
            for extra in extras:
                card.trailing.addWidget(extra)
            self.cards[spec.key] = card
            self.sections[spec.key] = card
            self.row.add(card)
        stack.addWidget(empty)
        stack.addWidget(self.row)
        self._row_stack = stack
        return holder

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """The main view takes at least 60% of the visible height; secondary
        sections that do not fit under it are a scroll away, never the result."""
        super().resizeEvent(event)
        if self.tabs is not None:
            visible = self.scroll_area.viewport().height()
            self.tabs.setMinimumHeight(max(MAIN_MIN_HEIGHT, int(visible * MAIN_SHARE)))

    # -- building --------------------------------------------------------
    def _content(self, spec: ViewWidget) -> tuple[QWidget, list[QWidget]]:
        """The bare view for ``spec`` (registered by key) and any buttons that
        belong in its heading."""
        if isinstance(spec, StatTiles):
            tiles = StatTilesWidget()
            self.tiles[spec.key] = tiles
            return tiles, []
        if isinstance(spec, BarChart):
            chart = BarChartWidget(spec)
            self.charts[spec.key] = chart
            return chart, [chart.toggle]
        if isinstance(spec, ResultsTable):
            _model, view, _caption = self._results_table(spec)
            return view, []
        if isinstance(spec, CardList):
            return self._card_list(spec), []
        if isinstance(spec, ImageView):
            image = ImageViewWidget()
            self.images[spec.key] = image
            return image, []
        if isinstance(spec, ActionTable):
            return self._action_table(spec), []
        if isinstance(spec, PagePreview):  # outside the tabs: its thumbnails switch parts
            preview = PagePreviewWidget()
            preview.setMinimumHeight(MAIN_MIN_HEIGHT)
            preview.open_requested.connect(self.open_requested.emit)
            self.page_previews[spec.key] = preview
            return preview, []
        text_view = self._text_view(spec)
        extras: list[QWidget] = []
        if spec.copy_button:
            extras.append(self._copy_button(spec.key, text_view))
        return text_view, extras

    def _top_section(self, spec: ViewWidget) -> QWidget:
        """A headline over the main view: no heading of its own, shown once filled."""
        content, _extras = self._content(spec)
        self.sections[spec.key] = content
        self._below_hidden.add(spec.key)
        content.setVisible(False)
        return content

    def _main_page(self, spec: ViewWidget) -> QWidget:
        page = QWidget()
        page.setObjectName("OutputPage")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(6)
        self.sections[spec.key] = page
        if isinstance(spec, ActionTable):  # has its own empty state
            layout.addWidget(self._action_table(spec))
            layout.addStretch(1)  # its buttons stay right under the rows
            return page
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)
        if isinstance(spec, ResultsTable):
            _model, view, caption = self._results_table(spec, fit=True)
            if spec.key in self.fit_tables:
                content_layout.addWidget(self.fit_tables[spec.key], 1)
            else:
                view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                content_layout.addWidget(view, 1)
                content_layout.addWidget(caption)
        elif isinstance(spec, CardList):
            content_layout.addWidget(self._card_list(spec), 1)
        elif isinstance(spec, ImageView):
            image = ImageViewWidget()
            self.images[spec.key] = image
            content_layout.addWidget(image, 1)
        elif isinstance(spec, StatTiles | BarChart):
            view_widget, extras = self._content(spec)
            content_layout.addWidget(view_widget)
            content_layout.addStretch(1)
            for extra in extras:
                self._corner.addWidget(extra)
                if isinstance(extra, QPushButton):
                    self.corner_buttons[spec.key] = extra
        else:
            assert isinstance(spec, TextView), spec  # a PagePreview takes its own tabs
            text_view = self._text_view(spec)
            content_layout.addWidget(text_view, 1)
            if spec.copy_button:
                self._corner.addWidget(self._copy_button(spec.key, text_view))
        empty = self._empty_label()
        empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.setWordWrap(True)
        stack = QStackedLayout()
        stack.addWidget(empty)
        stack.addWidget(content)
        layout.addLayout(stack, 1)
        self._waiting[spec.key] = stack
        return page

    def _below_section(self, spec: ViewWidget) -> QWidget:
        section = QWidget()
        section.setObjectName("OutputSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        head = QHBoxLayout()
        folded = isinstance(spec, ResultsTable) and spec.collapsed
        if isinstance(spec, ResultsTable) and spec.collapsed:
            head.addWidget(self._fold_button(spec))
        else:
            head.addWidget(eyebrow(spec.label))
        head.addStretch(1)
        layout.addLayout(head)
        self.sections[spec.key] = section
        if isinstance(spec, ActionTable):
            layout.addWidget(self._action_table(spec))
        elif isinstance(spec, ResultsTable):
            _model, view, caption = self._results_table(spec, fit=True)
            if spec.key in self.fit_tables:
                layout.addWidget(self.fit_tables[spec.key])
            else:
                layout.addWidget(view)
                layout.addWidget(caption)
            if folded:
                section.setObjectName("FoldSection")
                section.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
                layout.setContentsMargins(12, 6, 12, 6)
                self._table_body(spec.key).setVisible(False)
                caption.setVisible(False)
            self._below_hidden.add(spec.key)
        elif isinstance(spec, StatTiles | BarChart | PagePreview | CardList):
            content, extras = self._content(spec)
            layout.addWidget(content)
            for extra in extras:
                head.addWidget(extra)
            self._below_hidden.add(spec.key)
        elif isinstance(spec, ImageView):
            image = ImageViewWidget()
            image.setMinimumHeight(240)
            self.images[spec.key] = image
            layout.addWidget(image)
            self._below_hidden.add(spec.key)
        else:
            text_view = self._text_view(spec)
            text_view.setFixedHeight(BELOW_TEXT_MIN)  # fitted to its text once filled
            self._fit_below_text.add(spec.key)
            layout.addWidget(text_view)
            if spec.copy_button:
                head.addWidget(self._copy_button(spec.key, text_view))
        section.setVisible(spec.key not in self._below_hidden)
        return section

    def _details(self, *, fill: bool) -> QWidget:
        """The run log behind a one-line toggle at the pane's foot. A panel
        with no view of its own (only a log) opens it and lets it fill."""
        details = QWidget()
        details.setObjectName("Details")
        details.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QVBoxLayout(details)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        if fill:
            self.log_view.setMinimumHeight(MAIN_MIN_HEIGHT)
        else:
            self.log_view.setFixedHeight(LOG_HEIGHT)
        log_box = QWidget()
        box_layout = QVBoxLayout(log_box)
        box_layout.setContentsMargins(20, 10, 20, 0)
        box_layout.addWidget(self.log_view)
        self.log_box = log_box
        layout.addWidget(log_box, 1)

        bar = QWidget()
        bar.setObjectName("DetailsBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(20, 7, 20, 7)
        bar_layout.setSpacing(14)
        self.details_toggle = QPushButton(DETAILS_CLOSED)
        self.details_toggle.setObjectName("DetailsToggle")
        self.details_toggle.setCheckable(True)
        self.details_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.details_toggle.setToolTip("Show or hide the run log")
        self.details_toggle.toggled.connect(self._set_details_open)
        self.log_tail = ElidedLabel("run log")
        self.log_tail.setProperty("role", "faint")
        bar_layout.addWidget(self.details_toggle)
        bar_layout.addWidget(self.log_tail, 1)
        layout.addWidget(bar)

        opened = _details_open.get(self.details_key, fill)
        self.details_toggle.setChecked(opened)
        self._set_details_open(opened)
        return details

    def _set_details_open(self, opened: bool) -> None:
        self.details_toggle.setText(DETAILS_OPEN if opened else DETAILS_CLOSED)
        self.log_box.setVisible(opened)
        if self.details_key:
            _details_open[self.details_key] = opened

    @property
    def details_open(self) -> bool:
        return self.details_toggle.isChecked()

    def _results_table(
        self, spec: ResultsTable, *, fit: bool = False
    ) -> tuple[TableModel, TableWidget, QLabel]:
        """The model, view and caption for ``spec``; with ``fit`` (a tab or a
        section, not a report card) a table asked to fit the screen is also
        wrapped in a :class:`FitTable`, which holds the view and caption."""
        model = TableModel()
        view = TableWidget(model)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.set_hints(
            bars=spec.bars, tag_column=spec.tag_column, hidden_columns=spec.hidden_columns
        )
        caption = QLabel("")
        caption.setProperty("role", "faint")
        self.tables[spec.key] = (model, view, caption)
        if fit and (spec.compact or spec.lift_constants or spec.mark_changes or spec.pin_last):
            self.fit_tables[spec.key] = FitTable(spec, model, view, caption)
        return model, view, caption

    def _card_list(self, spec: CardList) -> CardListWidget:
        cards = CardListWidget(spec)
        self.card_lists[spec.key] = cards
        return cards

    def _fold_button(self, spec: ResultsTable) -> QPushButton:
        """The heading of a collapsed section: a toggle that opens and folds it."""
        button = QPushButton(f"{FOLD_CLOSED} {spec.label}")
        button.setProperty("role", "disclosure")
        button.setCheckable(True)
        button.setToolTip(spec.label)
        button.toggled.connect(lambda on, key=spec.key: self.set_folded(key, not on))
        self.folds[spec.key] = button
        return button

    def set_folded(self, key: str, folded: bool) -> None:
        """Fold or open a collapsed below section."""
        button = self.folds[key]
        _model, view, caption = self.tables[key]
        self._table_body(key).setVisible(not folded)
        caption.setVisible(not folded and bool(caption.text()))
        if button.isChecked() == folded:
            button.blockSignals(True)
            button.setChecked(not folded)
            button.blockSignals(False)
        spec = self._specs[key]
        rows = view.model().rowCount() if view.model() else 0
        count = f" · {rows} row{'s' if rows != 1 else ''}" if rows else ""
        button.setText(f"{FOLD_CLOSED if folded else FOLD_OPEN} {spec.label}{count}")

    def is_folded(self, key: str) -> bool:
        return not self._table_body(key).isVisibleTo(self.sections[key])

    def _table_body(self, key: str) -> QWidget:
        """What folds: the table view, or the fitted table holding it."""
        return self.fit_tables.get(key) or self.tables[key][1]

    def _action_table(self, spec: ActionTable) -> ActionTableWidget:
        widget = ActionTableWidget(spec)
        widget.action_requested.connect(self.action_requested.emit)
        self.action_tables[spec.key] = widget
        return widget

    def _text_view(self, spec: TextView) -> TextViewWidget | CodeViewWidget:
        text_view: TextViewWidget | CodeViewWidget
        if spec.code:  # numbered and highlighted, like the program it came from
            text_view = CodeViewWidget()
            text_view.setPlaceholderText("Nothing to show yet.")
        else:
            text_view = TextViewWidget(spec)
        self.text_views[spec.key] = text_view
        return text_view

    def _copy_button(self, key: str, view: QPlainTextEdit) -> QPushButton:
        copy = QPushButton("Copy")
        copy.setProperty("role", "ghost")
        copy.setToolTip("Copy the text to the clipboard")
        copy.clicked.connect(lambda _c=False, v=view: _copy_text(v))
        self.copy_buttons[key] = copy
        return copy

    def _show_corner(self, index: int) -> None:
        """Only the current tab's buttons (Copy, a chart's Table switch, a
        page preview's file name) show in the tab bar's corner. A page tab
        takes the preview widget into itself and shows its part."""
        current, part = self.tab_refs[index] if 0 <= index < len(self.tab_refs) else (None, None)
        for key, button in [*self.copy_buttons.items(), *self.corner_buttons.items()]:
            if key in self.main_keys:
                button.setVisible(key == current)
        for key, label in self.page_names.items():
            label.setVisible(key == current and bool(label.text()))
        if current in self.page_previews and part is not None:
            holder = self.sections[current]
            layouts = self._page_tabs[current]
            if layouts[part].indexOf(holder) < 0:
                for layout in layouts.values():
                    layout.removeWidget(holder)
                layouts[part].addWidget(holder)
                holder.show()
            preview = self.page_previews[current]
            if preview.part != part or preview.pages is None:
                preview.show_part(part)

    def _set_tab_visible(self, index: int, visible: bool) -> None:
        tabs = self.tabs
        if tabs is None or index < 0 or tabs.isTabVisible(index) == visible:
            return
        tabs.setTabVisible(index, visible)
        if not tabs.isTabVisible(tabs.currentIndex()):
            first = next((i for i in range(tabs.count()) if tabs.isTabVisible(i)), -1)
            if first >= 0:
                tabs.setCurrentIndex(first)

    # -- filling ---------------------------------------------------------
    def _apply_pages(self, key: str, result: RunResult, *, run: bool) -> None:
        pages = result.pages.get(key)
        sheet_tab, key_tab = self._tab_index(key, "sheet"), self._tab_index(key, "key")
        if pages is None:
            if run:
                self._set_tab_visible(sheet_tab, False)
                self._set_tab_visible(key_tab, False)
            return
        preview = self.page_previews[key]
        preview.set_pages(pages)
        self._filled(key)
        self._set_tab_visible(sheet_tab, True)
        self._set_tab_visible(key_tab, preview.has_part("key"))
        self._count_pages(key)
        self._name_page(key)
        if self.tabs is not None and sheet_tab >= 0:
            # A fresh result opens on the sheet's first page, unless the
            # teacher is looking at another view (trace's table).
            current = self.tabs.currentIndex()
            if self.tab_refs[current][0] == key and current != sheet_tab:
                self.tabs.setCurrentIndex(sheet_tab)
            else:
                self._show_corner(current)

    @staticmethod
    def _fit_text_height(view: QPlainTextEdit) -> None:
        """A secondary text (notes, a diff) takes the height of its lines, up
        to a limit past which it scrolls; the main view keeps the rest."""
        lines = max(view.blockCount(), 1)
        frame = view.frameWidth() * 2 + int(view.document().documentMargin() * 2) + 12
        wanted = lines * view.fontMetrics().lineSpacing() + frame
        view.setFixedHeight(max(BELOW_TEXT_MIN, min(BELOW_TEXT_MAX, wanted)))

    def _filled(self, key: str) -> None:
        stack = self._waiting.get(key)
        if stack is not None:
            stack.setCurrentIndex(1)
        if key in self._below_hidden:
            self.sections[key].show()
        if key in self.cards and self._row_stack is not None:
            self._row_stack.setCurrentIndex(1)

    def _emptied(self, key: str) -> None:
        stack = self._waiting.get(key)
        if stack is not None:
            stack.setCurrentIndex(0)
        if key in self._below_hidden:
            self.sections[key].hide()
        if key in self.cards and self._row_stack is not None:
            self._row_stack.setCurrentIndex(0)

    def _empty_label(self) -> QLabel:
        """A main view's stand-in until its first result: the run hint, or
        after a failed run its next step (:meth:`show_next_step`)."""
        empty = QLabel(self.empty_text)
        empty.setProperty("role", "placeholder")
        self.empty_labels.append(empty)
        return empty

    def _set_empty(self, text: str, role: str) -> None:
        for label in self.empty_labels:
            label.setText(text)
            label.setProperty("role", role)
            label.style().unpolish(label)
            label.style().polish(label)

    def show_next_step(self, text: str) -> None:
        """After a failed run: the views stand empty with what to do next in
        place of the run hint (``ToolError.next_step``), or nothing at all,
        never "Press Run" (#21)."""
        self._set_empty(text, "next-step")

    def clear(self) -> None:
        """Before a run: tables and images go back to their empty state (text
        views keep their last text until the new one arrives)."""
        self._set_empty(self.empty_text, "placeholder")
        for key, (model, _view, caption) in self.tables.items():
            model.set_table(None)
            caption.setText("")
            self._emptied(key)
        for key, card_list in self.card_lists.items():
            card_list.set_table(None)
            self._emptied(key)
        for key, image in self.images.items():
            image.set_image(None)
            self._emptied(key)
        for key, tiles in self.tiles.items():
            tiles.set_stats([])
            self._emptied(key)
        for key, chart in self.charts.items():
            chart.set_table(None)
            self._emptied(key)
        for key, preview in self.page_previews.items():
            preview.clear()  # let go of the files before the run rewrites them
            self._emptied(key)
            self._count_pages(key)
            self._name_page(key)
        self.log_view.clear()
        self.log_tail.setText("run log")

    def append_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)
        last = line.strip().splitlines()[-1] if line.strip() else ""
        if last:
            self.log_tail.setText(last)

    def busy(self) -> bool:
        """Whether a page preview is still drawing thumbnails."""
        return any(p.busy() for p in self.page_previews.values())

    def apply(self, result: RunResult, *, run: bool = True) -> None:
        """Fill the views ``result`` has values for. ``run`` (a run, not a row
        action or a refresh) also hides the views that are only shown while
        filled: page previews without pages, optional text views."""
        for key, widget in self.action_tables.items():
            table = result.tables.get(key)
            if table is not None:
                widget.set_table(table)
        for key, text_view in self.text_views.items():
            text = result.texts.get(key)
            if text is not None:
                text_view.set_text(text)
                if key in self._fit_below_text:
                    self._fit_text_height(text_view)
                self._filled(key)
            if key in self._optional and (text is not None or run):
                self._set_tab_visible(self._tab_index(key), text is not None)
        for key in self.page_previews:
            self._apply_pages(key, result, run=run)
        for key, (model, view, caption) in self.tables.items():
            table = result.tables.get(key)
            if table is None:
                continue
            model.set_table(table)
            view.apply_hints()
            spec = self._specs.get(key)
            hinted = isinstance(spec, ResultsTable) and bool(spec.bars or spec.tag_column)
            rows, cols = table.shape
            if key in self.fit_tables:  # sizes itself and says what its marks mean
                self.fit_tables[key].refresh()
                if key not in self.main_keys:
                    view.fit_rows(BELOW_TABLE_ROWS)
            elif hinted:
                view.fit_columns(min_width=COMPACT_COLUMN, extra=0)
            else:
                view.fit_columns()
            if key in self.cards:  # a report's table: every row, no caption
                view.fit_rows(ROW_TABLE_ROWS)
                caption.setText("")
                caption.hide()
            elif key not in self.fit_tables:
                if key not in self.main_keys:
                    view.fit_rows(BELOW_TABLE_ROWS)
                caption.setText(f"{rows} rows × {cols} columns")
            self._filled(key)
            if key in self.folds:
                self.set_folded(key, True)  # a fresh result starts folded again
        for key, card_list in self.card_lists.items():
            table = result.tables.get(key)
            if table is not None:
                card_list.set_table(table)
                self._filled(key)
        for key, tiles in self.tiles.items():
            table = result.tables.get(key)
            if table is not None:
                tiles.set_stats(stats_from_table(table))
                self._filled(key)
        for key, chart in self.charts.items():
            table = result.tables.get(key)
            if table is not None:
                chart.set_table(table)
                if key in self.cards:
                    self.cards[key].set_caption(result.texts.get(key, ""))
                self._filled(key)
        if self.row is not None:
            self.row.relayout()
        for key, image in self.images.items():
            path = result.images.get(key)
            if path is None:
                continue
            image.set_image(path)
            self._filled(key)
        if result.summary:
            self.append_log(result.summary)
