"""The preview pane: code, text, image or PDF text for parseable kinds; an
open-externally card for everything else; tags and notes underneath."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.library.extract import CloudOnlyError, read_pdf_text, read_text
from staffroom.core.library.model import Resource
from staffroom.core.library.service import LibraryService
from staffroom.core.log import get_logger
from staffroom.shell.library.highlighter import PythonHighlighter
from staffroom.shell.library.result_item import KIND_LABEL
from staffroom.shell.theme import Palette, palette
from staffroom.shell.widgets import Card, ImageViewWidget, make_label

log = get_logger(__name__)

OFFICE_APP = {
    ".doc": "Word",
    ".docx": "Word",
    ".ppt": "PowerPoint",
    ".pptx": "PowerPoint",
    ".pub": "Publisher",
    ".xls": "Excel",
    ".xlsx": "Excel",
    ".key": "Keynote",
    ".pages": "Pages",
    ".numbers": "Numbers",
}


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


class PreviewPane(QWidget):
    tags_saved = Signal(str)

    def __init__(self, service: LibraryService, theme: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.resource: Resource | None = None
        self._palette: Palette = palette(theme)  # type: ignore[arg-type]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedLayout()
        outer.addLayout(self.stack)

        self.empty = QLabel("Pick a file in the sidebar, or search.")
        self.empty.setProperty("role", "empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.empty)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        scroll.setWidget(body)
        self.stack.addWidget(scroll)

        # -- header
        head = QVBoxLayout()
        head.setSpacing(4)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self.title = make_label("", "title")
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.chip = QLabel("")
        self.chip.setProperty("role", "chip")
        title_row.addWidget(self.title)
        title_row.addWidget(self.chip, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch(1)
        self.open_button = QPushButton("Open externally")
        self.open_button.setProperty("role", "primary")
        self.open_button.clicked.connect(self.open_externally)
        self.reveal_button = QPushButton("Reveal in Finder")
        self.reveal_button.clicked.connect(self.reveal)
        title_row.addWidget(self.reveal_button)
        title_row.addWidget(self.open_button)
        head.addLayout(title_row)
        self.meta = make_label("", "subtitle")
        self.meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        head.addWidget(self.meta)
        layout.addLayout(head)

        self.cloud_banner = QLabel(
            "Cloud-only: this file is not downloaded on this Mac. Open externally to fetch it."
        )
        self.cloud_banner.setProperty("role", "danger")
        self.cloud_banner.setWordWrap(True)
        self.cloud_banner.hide()
        layout.addWidget(self.cloud_banner)
        self.withheld_banner = QLabel(
            "Indexed by name only: the text looks like it holds pupil details (a candidate "
            "number, surname, UPN or date of birth next to a value), so it was not copied into "
            "the index. Exclude the folder in Settings, or keep such files out of the "
            "resources folder."
        )
        self.withheld_banner.setProperty("role", "danger")
        self.withheld_banner.setWordWrap(True)
        self.withheld_banner.hide()
        layout.addWidget(self.withheld_banner)

        # -- content
        self.content_card = Card()
        self.content = QStackedLayout()
        self.content_card.body.addLayout(self.content)

        self.code = QPlainTextEdit()
        self.code.setObjectName("CodeView")
        self.code.setReadOnly(True)
        self.code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.code.setMinimumHeight(360)
        self.highlighter: PythonHighlighter | None = None
        self.content.addWidget(self.code)

        self.text = QPlainTextEdit()
        self.text.setObjectName("TextView")
        self.text.setReadOnly(True)
        self.text.setMinimumHeight(360)
        self.content.addWidget(self.text)

        self.image = ImageViewWidget()
        self.image.setMinimumHeight(360)
        self.content.addWidget(self.image)

        self.card = QWidget()
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(0, 24, 0, 24)
        card_layout.setSpacing(10)
        self.card_title = make_label("", "section")
        self.card_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_text = make_label("", "muted", wrap=True)
        self.card_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_button = QPushButton("Open externally")
        self.card_button.setProperty("role", "primary")
        self.card_button.clicked.connect(self.open_externally)
        card_layout.addWidget(self.card_title)
        card_layout.addWidget(self.card_text)
        card_layout.addWidget(self.card_button, 0, Qt.AlignmentFlag.AlignHCenter)
        self.content.addWidget(self.card)
        layout.addWidget(self.content_card)

        # -- tags
        tags_card = Card(
            "Tags and notes", "Saved to the sidecar file; the resource itself is never changed."
        )
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("comma-separated, e.g. loops, ks3, starter")
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText("Notes for future you…")
        self.notes_edit.setFixedHeight(72)
        save_row = QHBoxLayout()
        self.save_button = QPushButton("Save tags")
        self.save_button.clicked.connect(self.save_tags)
        self.save_status = make_label("", "faint")
        save_row.addWidget(self.save_button)
        save_row.addWidget(self.save_status, 1)
        tags_card.add(self.tags_edit)
        tags_card.add(self.notes_edit)
        tags_card.body.addLayout(save_row)
        layout.addWidget(tags_card)
        layout.addStretch(1)

    # -- theming ---------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        self._palette = palette(theme)  # type: ignore[arg-type]
        if self.resource and self.resource.kind == "python":
            self._highlight()

    def _highlight(self) -> None:
        if self.highlighter is not None:
            self.highlighter.setDocument(None)
        self.highlighter = PythonHighlighter(self.code.document(), self._palette)

    # -- showing ---------------------------------------------------------
    def clear(self) -> None:
        self.resource = None
        self.stack.setCurrentWidget(self.empty)

    def show_resource(self, resource: Resource) -> None:
        self.resource = resource
        path = self.service.absolute(resource.rel_path)
        self.title.setText(resource.name)
        self.chip.setText(KIND_LABEL.get(resource.kind, resource.kind))
        modified = datetime.fromtimestamp(resource.mtime).strftime("%d %b %Y, %H:%M")
        self.meta.setText(f"{resource.rel_path}   ·   {human_size(resource.size)}   ·   {modified}")
        self.cloud_banner.setVisible(resource.cloud_only)
        self.withheld_banner.setVisible(resource.text_withheld)
        self.stack.setCurrentIndex(1)

        entry = self.service.tag_entry(resource.rel_path)
        self.tags_edit.setText(", ".join(entry.tags))
        self.notes_edit.setPlainText(entry.notes)
        self.save_status.setText("")

        if resource.cloud_only or resource.external_only:
            self._show_card(resource, path)
        elif resource.kind == "image":
            self.image.set_image(path)
            self.content.setCurrentWidget(self.image)
        elif resource.kind == "pdf":
            self._show_text(self._safe(lambda: read_pdf_text(path, page_cap=1), path), pdf=True)
        elif resource.kind == "python":
            self.code.setPlainText(self._safe(lambda: read_text(path), path))
            self._highlight()
            self.content.setCurrentWidget(self.code)
        else:
            self._show_text(self._safe(lambda: read_text(path), path))

    def _safe(self, reader: Callable[[], str], path: Path) -> str:
        try:
            return reader()
        except CloudOnlyError:
            self.cloud_banner.show()
            return ""
        except OSError as exc:
            log.warning("preview failed for %s: %s", path, exc)
            return f"Could not read {path.name}: {exc}"

    def _show_text(self, text: str, *, pdf: bool = False) -> None:
        if pdf and not text.strip():
            text = "No text layer on the first page (scanned PDF?). Open externally to view it."
        elif pdf:
            text = "First page text:\n\n" + text
        self.text.setPlainText(text)
        self.content.setCurrentWidget(self.text)

    def _show_card(self, resource: Resource, path: Path) -> None:
        app = OFFICE_APP.get(resource.ext)
        self.card_title.setText(
            KIND_LABEL.get(resource.kind, "File") + (f" · {app}" if app else "")
        )
        if resource.cloud_only:
            text = "Not downloaded on this Mac. Opening it asks iCloud to fetch the file."
        elif resource.kind == "office":
            text = (
                "Office files are never parsed by Staffroom. "
                f"This opens {path.name} in {app or 'its native app'}."
            )
        else:
            kind = KIND_LABEL.get(resource.kind, "this kind").lower()
            text = f"No preview for {kind} files. Opens in its native app."
        self.card_text.setText(text)
        self.content.setCurrentWidget(self.card)

    # -- actions ---------------------------------------------------------
    def open_externally(self) -> None:
        if self.resource:
            self.service.open_externally(self.service.absolute(self.resource.rel_path))

    def reveal(self) -> None:
        if self.resource:
            self.service.reveal(self.service.absolute(self.resource.rel_path))

    def save_tags(self) -> None:
        if not self.resource:
            return
        entry = self.service.set_tags(
            self.resource.rel_path, self.tags_edit.text(), self.notes_edit.toPlainText()
        )
        self.tags_edit.setText(", ".join(entry.tags))
        self.save_status.setText("Saved")
        self.tags_saved.emit(self.resource.rel_path)
