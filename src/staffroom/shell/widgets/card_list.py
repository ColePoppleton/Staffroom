"""One card per row (:class:`~staffroom.core.panel.CardList`): a short list
whose rows each say several things, shown without sideways scrolling.

Each card is a heading (the title in bold, the details muted, the badge at
the right in its tone) over code lines in a diff's two inks. The badge keeps
its full width; the last detail wraps instead, and a code line too long for
the card is cut with an ellipsis and shown in full on hover.

The list keeps its rows in a :class:`TableModel` with a
``QItemSelectionModel`` and answers ``model()``, ``selectionModel()``,
``selectRow()`` and ``scrollTo()`` as a table view does, so a
:class:`LineLink` joins cards to lines of code exactly as it joins table rows.
Up / Down / Home / End move the selection when the list has focus."""

from __future__ import annotations

from collections.abc import Mapping

from PySide6.QtCore import (
    QItemSelection,
    QItemSelectionModel,
    QModelIndex,
    QPersistentModelIndex,
    QPoint,
    Qt,
    Signal,
)
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.panel import CardList, card_text
from staffroom.core.table import Cell, Table
from staffroom.shell.widgets.elided_label import ElidedLabel
from staffroom.shell.widgets.table_view import TableModel

CARD_SPACING = 9


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class ResultCard(QFrame):
    """One row as a card. Emits ``clicked(row)`` when pressed anywhere on it."""

    clicked = Signal(int)

    def __init__(self, spec: CardList, record: Mapping[str, Cell], parent: QWidget | None = None):
        super().__init__(parent)
        self.row = 0  # its row in the list, set by the list
        self.setObjectName("ResultCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(7)

        head = QHBoxLayout()
        head.setSpacing(10)
        self.title = QLabel(card_text(spec.title, record))
        self.title.setObjectName("CardTitle")
        head.addWidget(self.title, 0, Qt.AlignmentFlag.AlignTop)
        details = [t for t in (card_text(d, record) for d in spec.details) if t]
        self.details: list[QLabel] = []
        for i, text in enumerate(details):
            label = QLabel(text)
            label.setObjectName("CardDetail")
            last = i == len(details) - 1
            if last:  # wraps rather than push the badge out
                label.setWordWrap(True)
                label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            head.addWidget(label, 1 if last else 0, Qt.AlignmentFlag.AlignTop)
            self.details.append(label)
        if not details:
            head.addStretch(1)
        self.badge: QLabel | None = None
        if spec.badge is not None:
            value = record.get(spec.badge)
            badge = QLabel("" if value is None else str(value))
            badge.setObjectName("CardBadge")
            tone = spec.tone(record.get(spec.tone_column) if spec.tone_column else None)
            badge.setProperty("tone", tone)
            badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            head.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
            self.badge = badge
        layout.addLayout(head)

        self.code: list[ElidedLabel] = []
        for i, (caption, column) in enumerate(spec.code_lines):
            value = record.get(column)
            line = QFrame()
            line.setObjectName("CardCodeLine")
            line.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
            line.setProperty("diff", "old" if i == 0 and len(spec.code_lines) > 1 else "new")
            row = QHBoxLayout(line)
            row.setContentsMargins(8, 1, 8, 1)
            row.setSpacing(10)
            cap = QLabel(caption)
            cap.setObjectName("CardCodeCaption")
            code = ElidedLabel("" if value is None else str(value))
            code.setObjectName("CardCode")
            code.setTextFormat(Qt.TextFormat.PlainText)
            row.addWidget(cap)
            row.addWidget(code, 1)
            layout.addWidget(line)
            self.code.append(code)

    def set_selected(self, selected: bool) -> None:
        if bool(self.property("selected")) != selected:
            self.setProperty("selected", selected)
            _repolish(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.row)
        super().mousePressEvent(event)


class CardListWidget(QScrollArea):
    """The cards of one :class:`CardList`, filled with :meth:`set_table`."""

    def __init__(self, spec: CardList, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setObjectName("CardList")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._model = TableModel()
        self._selection = QItemSelectionModel(self._model)
        self._selection.selectionChanged.connect(self._show_selection)
        body = QWidget()
        body.setObjectName("CardListBody")
        self._box = QVBoxLayout(body)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(CARD_SPACING)
        self._box.addStretch(1)
        self.setWidget(body)
        self.cards: list[ResultCard] = []

    # -- the view API a LineLink uses ----------------------------------------
    def model(self) -> TableModel:
        return self._model

    def selectionModel(self) -> QItemSelectionModel:  # noqa: N802
        return self._selection

    def selectRow(self, row: int) -> None:  # noqa: N802
        """Select card ``row`` (0-based) alone and bring it into view."""
        if not 0 <= row < len(self.cards):
            return
        model = self._model
        selection = QItemSelection(model.index(row, 0), model.index(row, model.columnCount() - 1))
        flags = QItemSelectionModel.SelectionFlag.ClearAndSelect
        self._selection.select(selection, flags)
        self._selection.setCurrentIndex(
            model.index(row, 0), QItemSelectionModel.SelectionFlag.NoUpdate
        )
        self.ensureWidgetVisible(self.cards[row], 0, CARD_SPACING)

    def scrollTo(self, index: QModelIndex | QPersistentModelIndex) -> None:  # noqa: N802
        if index.isValid() and index.row() < len(self.cards):
            self.ensureWidgetVisible(self.cards[index.row()], 0, CARD_SPACING)

    # -- filling ------------------------------------------------------------
    def set_table(self, table: Table | None) -> None:
        self._selection.clearSelection()  # a link lets go of its line
        for card in self.cards:
            self._box.removeWidget(card)
            card.deleteLater()
        self.cards = []
        self._model.set_table(table)
        if table is None:
            return
        for row, record in enumerate(table.to_dicts()):
            card = ResultCard(self.spec, record)
            card.row = row
            card.clicked.connect(self._card_clicked)
            self._box.insertWidget(row, card)
            self.cards.append(card)
        self.verticalScrollBar().setValue(0)

    def count(self) -> int:
        return len(self.cards)

    def selected_rows(self) -> list[int]:
        return sorted({i.row() for i in self._selection.selectedIndexes()})

    def _card_clicked(self, row: int) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.selectRow(row)

    def _show_selection(self, *_: object) -> None:
        chosen = set(self.selected_rows())
        for row, card in enumerate(self.cards):
            card.set_selected(row in chosen)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self.cards:
            super().keyPressEvent(event)
            return
        current = self._selection.currentIndex().row()
        rows = self.selected_rows()
        if current < 0 and rows:
            current = rows[0]
        last = len(self.cards) - 1
        key = event.key()
        target = {
            Qt.Key.Key_Down: min(current + 1, last) if current >= 0 else 0,
            Qt.Key.Key_Up: max(current - 1, 0) if current >= 0 else 0,
            Qt.Key.Key_Home: 0,
            Qt.Key.Key_End: last,
        }.get(Qt.Key(key))
        if target is None:
            super().keyPressEvent(event)
            return
        self.selectRow(target)
        event.accept()

    # -- reading (tests, the probe) -----------------------------------------
    def visible_badges(self) -> int:
        """How many cards show their badge whole inside the visible area."""
        viewport = self.viewport()
        area = viewport.rect()
        seen = 0
        for card in self.cards:
            badge = card.badge
            if badge is None or not badge.isVisibleTo(self):
                continue
            top_left = badge.mapTo(viewport, QPoint(0, 0))
            rect = badge.rect().translated(top_left)
            whole = badge.width() >= badge.sizeHint().width()
            if whole and area.contains(rect):
                seen += 1
        return seen
