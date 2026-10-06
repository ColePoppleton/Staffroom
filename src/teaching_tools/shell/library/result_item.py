"""One search hit rendered as a rich list row: name, kind chip, folder, snippet."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from teaching_tools.core.library.model import Resource, SearchHit

KIND_LABEL = {
    "python": "Python",
    "text": "Text",
    "markdown": "Markdown",
    "csv": "CSV",
    "pdf": "PDF",
    "image": "Image",
    "office": "Office document",
    "scratch": "Scratch project",
    "audio": "Audio",
    "video": "Video",
    "archive": "Archive",
    "database": "Database",
    "diagram": "Diagram",
    "other": "File",
}


ROW_MARGIN = 8
NAME_LINE = 24  # name + kind chip
TEXT_LINE = 17  # folder / snippet lines


class ResultItem(QWidget):
    """Fixed-height rows: Qt's size hints are unreliable before a list is
    shown, and a predictable height keeps the list tidy."""

    def __init__(self, resource: Resource, snippet: str = "") -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, ROW_MARGIN, 12, ROW_MARGIN)
        layout.setSpacing(2)
        lines = 2 + (1 if snippet else 0)
        self.row_height = 2 * ROW_MARGIN + NAME_LINE + (lines - 1) * (TEXT_LINE + 2)
        self.setFixedHeight(self.row_height)
        top = QHBoxLayout()
        top.setSpacing(8)
        name = QLabel(resource.name)
        name.setObjectName("ToolName")
        chip = QLabel(KIND_LABEL.get(resource.kind, resource.kind))
        chip.setProperty("role", "chip")
        top.addWidget(name)
        top.addWidget(chip)
        top.addStretch(1)
        layout.addLayout(top)
        folder = resource.rel_path.rpartition("/")[0] or "/"
        path = QLabel(folder + ("   ☁︎ cloud-only" if resource.cloud_only else ""))
        path.setObjectName("ToolDesc")
        layout.addWidget(path)
        if snippet:
            # One line, clipped, so every row has a predictable height.
            text = snippet if len(snippet) <= SNIPPET_CHARS else snippet[: SNIPPET_CHARS - 1] + "…"
            snip = QLabel(text)
            snip.setProperty("role", "faint")
            snip.setWordWrap(False)
            snip.setToolTip(snippet)
            layout.addWidget(snip)

    @classmethod
    def from_hit(cls, hit: SearchHit) -> ResultItem:
        return cls(hit.resource, hit.snippet)


SNIPPET_CHARS = 110


def add_result_row(list_widget: QListWidget, hit: SearchHit, role: int) -> QListWidgetItem:
    """Append a rich, fixed-height row."""
    item = QListWidgetItem()
    item.setData(role, hit.resource.rel_path)
    widget = ResultItem.from_hit(hit)
    item.setSizeHint(QSize(0, widget.row_height))
    list_widget.addItem(item)
    list_widget.setItemWidget(item, widget)
    return item


def no_matches_row(list_widget: QListWidget) -> QListWidgetItem:
    item = QListWidgetItem("No matches")
    item.setFlags(Qt.ItemFlag.NoItemFlags)
    list_widget.addItem(item)
    return item
