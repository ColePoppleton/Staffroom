"""The right-hand side of the workbench: a panel's output widgets, filled from
a RunResult.

Top to bottom:

* ``strip_slot``: an empty layout on the pane's top edge, kept for the result
  strip (#84) that will say what the run did and which files it wrote.
* The main view: one tab per main output (see :func:`core.panel.main_outputs`).
  A single main output still gets its one tab, so the title sits in the same
  place in every tool. Each tab shows a short hint until its first result.
* Secondary outputs (ActionTable lists, notes) as sections under the main view.
* The run log, until the result strip replaces it (#84).

The pane scrolls as a whole only when the secondary sections do not fit; the
main view always starts at the top, so a result never lands below the fold.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
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
    ImageView,
    LogArea,
    OutputWidget,
    ResultsTable,
    TextView,
    ViewWidget,
    below_outputs,
    main_outputs,
)
from staffroom.core.plugin import RunResult
from staffroom.shell.widgets.action_table import ActionTableWidget
from staffroom.shell.widgets.image_view import ImageViewWidget
from staffroom.shell.widgets.input_group import eyebrow
from staffroom.shell.widgets.table_view import TableModel, TableWidget
from staffroom.shell.widgets.text_view import TextViewWidget

MAIN_MIN_HEIGHT = 300  # the main view never shrinks below this; the pane scrolls instead
MAIN_SHARE = 0.6  # ...nor below this share of the visible height
BELOW_TABLE_ROWS = 8
LOG_HEIGHT = 96
BELOW_TEXT_MIN, BELOW_TEXT_MAX = 72, 240


def _copy_text(view: QPlainTextEdit) -> None:
    QApplication.clipboard().setText(view.toPlainText())


class OutputPane(QWidget):
    action_requested = Signal(str, object)  # from any ActionTable: name, row dict

    def __init__(
        self,
        outputs: tuple[OutputWidget, ...],
        parent: QWidget | None = None,
        *,
        empty_text: str = "Results appear here after a run.",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("OutputPane")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.tables: dict[str, tuple[TableModel, TableWidget, QLabel]] = {}
        self.action_tables: dict[str, ActionTableWidget] = {}
        self.text_views: dict[str, TextViewWidget] = {}
        self.images: dict[str, ImageViewWidget] = {}
        self.copy_buttons: dict[str, QPushButton] = {}
        self.log_view: QPlainTextEdit | None = None
        # Each view's container: its tab page (main) or its section (below).
        self.sections: dict[str, QWidget] = {}
        self.empty_text = empty_text
        self._waiting: dict[str, QStackedLayout] = {}  # main views before their first result
        self._below_hidden: set[str] = set()  # below sections shown once filled
        self._fit_below_text: set[str] = set()  # below text views sized to their text
        main = main_outputs(outputs)
        self.main_keys = [w.key for w in main]

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # The pane's top edge: kept free for the result strip (#84).
        self.strip_slot = QVBoxLayout()
        self.strip_slot.setContentsMargins(0, 0, 0, 0)
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

        self.tabs = QTabWidget()
        self.tabs.setObjectName("OutputTabs")
        bar = self.tabs.tabBar()
        bar.setDrawBase(False)  # the pane's top border is the one hairline
        bar.setExpanding(False)
        bar.setUsesScrollButtons(False)
        bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.setMinimumHeight(MAIN_MIN_HEIGHT)
        corner = QWidget()
        corner.setObjectName("TabCorner")
        self._corner = QHBoxLayout(corner)
        self._corner.setContentsMargins(0, 0, 0, 4)
        self._corner.setSpacing(6)
        for spec in main:
            index = self.tabs.addTab(self._main_page(spec), spec.label)
            self.tabs.setTabToolTip(index, spec.label)
        self.tabs.setCornerWidget(corner, Qt.Corner.TopRightCorner)
        self.tabs.currentChanged.connect(self._show_corner)
        self._show_corner(self.tabs.currentIndex())
        self.body_layout.addWidget(self.tabs, 1)
        self.tabs.setVisible(bool(main))

        for spec in below_outputs(outputs):
            self.body_layout.addWidget(self._below_section(spec))

        for log_spec in (o for o in outputs if isinstance(o, LogArea)):
            self.body_layout.addWidget(self._log_section(log_spec, fill=not main))
        if not main:
            self.body_layout.addStretch(1)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """The main view takes at least 60% of the visible height; secondary
        sections that do not fit under it are a scroll away, never the result."""
        super().resizeEvent(event)
        visible = self.scroll_area.viewport().height()
        self.tabs.setMinimumHeight(max(MAIN_MIN_HEIGHT, int(visible * MAIN_SHARE)))

    # -- building --------------------------------------------------------
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
            _model, view, caption = self._results_table(spec)
            view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            content_layout.addWidget(view, 1)
            content_layout.addWidget(caption)
        elif isinstance(spec, ImageView):
            image = ImageViewWidget()
            self.images[spec.key] = image
            content_layout.addWidget(image, 1)
        else:
            text_view = self._text_view(spec)
            content_layout.addWidget(text_view, 1)
            if spec.copy_button:
                self._corner.addWidget(self._copy_button(spec.key, text_view))
        empty = QLabel(self.empty_text)
        empty.setProperty("role", "placeholder")
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
        head.addWidget(eyebrow(spec.label))
        head.addStretch(1)
        layout.addLayout(head)
        self.sections[spec.key] = section
        if isinstance(spec, ActionTable):
            layout.addWidget(self._action_table(spec))
        elif isinstance(spec, ResultsTable):
            _model, view, caption = self._results_table(spec)
            layout.addWidget(view)
            layout.addWidget(caption)
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

    def _log_section(self, spec: LogArea, *, fill: bool) -> QWidget:
        section = QWidget()
        section.setObjectName("OutputSection")
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(eyebrow(spec.label))
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("LogView")
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)
        if fill:
            self.log_view.setMinimumHeight(MAIN_MIN_HEIGHT)
        else:
            self.log_view.setFixedHeight(LOG_HEIGHT)
        layout.addWidget(self.log_view)
        self.sections[spec.key] = section
        return section

    def _results_table(self, spec: ResultsTable) -> tuple[TableModel, TableWidget, QLabel]:
        model = TableModel()
        view = TableWidget(model)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        caption = QLabel("")
        caption.setProperty("role", "faint")
        self.tables[spec.key] = (model, view, caption)
        return model, view, caption

    def _action_table(self, spec: ActionTable) -> ActionTableWidget:
        widget = ActionTableWidget(spec)
        widget.action_requested.connect(self.action_requested.emit)
        self.action_tables[spec.key] = widget
        return widget

    def _text_view(self, spec: TextView) -> TextViewWidget:
        text_view = TextViewWidget(spec)
        self.text_views[spec.key] = text_view
        return text_view

    def _copy_button(self, key: str, view: TextViewWidget) -> QPushButton:
        copy = QPushButton("Copy")
        copy.setProperty("role", "ghost")
        copy.setToolTip("Copy the text to the clipboard")
        copy.clicked.connect(lambda _c=False, v=view: _copy_text(v))
        self.copy_buttons[key] = copy
        return copy

    def _show_corner(self, index: int) -> None:
        """Only the current tab's Copy button shows in the tab bar's corner."""
        current = self.main_keys[index] if 0 <= index < len(self.main_keys) else None
        for key, button in self.copy_buttons.items():
            if key in self.main_keys:
                button.setVisible(key == current)

    # -- filling ---------------------------------------------------------
    @staticmethod
    def _fit_text_height(view: TextViewWidget) -> None:
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

    def _emptied(self, key: str) -> None:
        stack = self._waiting.get(key)
        if stack is not None:
            stack.setCurrentIndex(0)
        if key in self._below_hidden:
            self.sections[key].hide()

    def clear(self) -> None:
        """Before a run: tables and images go back to their empty state (text
        views keep their last text until the new one arrives)."""
        for key, (model, _view, caption) in self.tables.items():
            model.set_table(None)
            caption.setText("")
            self._emptied(key)
        for key, image in self.images.items():
            image.set_image(None)
            self._emptied(key)
        if self.log_view:
            self.log_view.clear()

    def append_log(self, line: str) -> None:
        if self.log_view:
            self.log_view.appendPlainText(line)

    def apply(self, result: RunResult) -> None:
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
        for key, (model, view, caption) in self.tables.items():
            table = result.tables.get(key)
            if table is None:
                continue
            model.set_table(table)
            view.fit_columns()
            if key not in self.main_keys:
                view.fit_rows(BELOW_TABLE_ROWS)
            rows, cols = table.shape
            caption.setText(f"{rows} rows × {cols} columns")
            self._filled(key)
        for key, image in self.images.items():
            path = result.images.get(key)
            if path is None:
                continue
            image.set_image(path)
            self._filled(key)
        if result.summary:
            self.append_log(result.summary)
