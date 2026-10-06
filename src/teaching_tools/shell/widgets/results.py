"""Renders a panel's output widgets and fills them from a RunResult."""

from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from teaching_tools.core.panel import ImageView, LogArea, OutputWidget, ResultsTable
from teaching_tools.core.plugin import RunResult
from teaching_tools.shell.widgets.card import Card
from teaching_tools.shell.widgets.image_view import ImageViewWidget
from teaching_tools.shell.widgets.table_view import TableModel, TableWidget


class ResultsArea(QWidget):
    def __init__(self, outputs: tuple[OutputWidget, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.tables: dict[str, tuple[TableModel, TableWidget, QLabel]] = {}
        self.images: dict[str, ImageViewWidget] = {}
        self.log_view: QPlainTextEdit | None = None
        self.cards: dict[str, Card] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        for spec in outputs:
            card = Card(spec.label)
            self.cards[spec.key] = card
            if isinstance(spec, ResultsTable):
                model = TableModel()
                view = TableWidget(model)
                view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
                caption = QLabel("")
                caption.setProperty("role", "faint")
                card.add(view)
                card.add(caption)
                self.tables[spec.key] = (model, view, caption)
                card.hide()  # shown once there is a result
            elif isinstance(spec, ImageView):
                image = ImageViewWidget()
                card.add(image)
                self.images[spec.key] = image
                card.hide()
            elif isinstance(spec, LogArea):
                self.log_view = QPlainTextEdit()
                self.log_view.setObjectName("LogView")
                self.log_view.setReadOnly(True)
                self.log_view.setMaximumBlockCount(2000)
                self.log_view.setFixedHeight(140)
                card.add(self.log_view)
            layout.addWidget(card)

    def clear(self) -> None:
        for key, (model, _view, caption) in self.tables.items():
            model.set_table(None)
            caption.setText("")
            self.cards[key].hide()
        for key, image in self.images.items():
            image.set_image(None)
            self.cards[key].hide()
        if self.log_view:
            self.log_view.clear()

    def append_log(self, line: str) -> None:
        if self.log_view:
            self.log_view.appendPlainText(line)

    def apply(self, result: RunResult) -> None:
        for key, (model, view, caption) in self.tables.items():
            table = result.tables.get(key)
            if table is None:
                continue
            model.set_table(table)
            view.fit_columns()
            view.fit_rows(15)
            rows, cols = table.shape
            caption.setText(f"{rows} rows × {cols} columns")
            self.cards[key].show()
        for key, image in self.images.items():
            path = result.images.get(key)
            if path is None:
                continue
            image.set_image(path)
            self.cards[key].show()
        if result.summary:
            self.append_log(result.summary)
