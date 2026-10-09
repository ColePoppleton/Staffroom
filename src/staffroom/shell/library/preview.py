"""The preview pane: the file's title, its tags as chips and the use bar
over the file itself (code, text, image or PDF text for parseable kinds; a
short card saying why not for everything else, which is never parsed)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.library.extract import CloudOnlyError, read_pdf_text, read_text
from staffroom.core.library.model import Resource
from staffroom.core.library.service import LibraryService
from staffroom.core.log import get_logger
from staffroom.shell.library.result_item import KIND_LABEL
from staffroom.shell.library.tag_chips import TagChips
from staffroom.shell.library.use_bar import UseBar
from staffroom.shell.widgets import ImageViewWidget, make_label
from staffroom.shell.widgets.code_view import CodeViewWidget
from staffroom.shell.widgets.elided_label import ElidedLabel

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
    """One file, top to bottom: its name and where it lives (with the quiet
    *Open externally* / *Reveal* beside them), its tags as chips, the use bar,
    then the file itself filling the rest."""

    tags_saved = Signal(str)

    def __init__(self, service: LibraryService, theme: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.resource: Resource | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedLayout()
        outer.addLayout(self.stack)

        self.empty = QLabel("Pick a file on the left, or search.")
        self.empty.setProperty("role", "empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.stack.addWidget(self.empty)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        self.stack.addWidget(body)

        # -- the title line: name, where it lives, the quiet actions
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        self.title = make_label("", "file-title")
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # Folder, size and date: elided, so a deep folder never widens the window.
        self.meta = ElidedLabel(mode=Qt.TextElideMode.ElideMiddle)
        self.meta.setProperty("role", "subtitle")
        title_row.addWidget(self.title, 0, Qt.AlignmentFlag.AlignBaseline)
        title_row.addWidget(self.meta, 1, Qt.AlignmentFlag.AlignBaseline)
        self.open_button = QPushButton("Open externally")
        self.open_button.setProperty("role", "ghost")
        self.open_button.setToolTip("Open the original in its own app (⌘O opens a copy for class)")
        self.open_button.clicked.connect(self.open_externally)
        self.reveal_button = QPushButton("Reveal")
        self.reveal_button.setProperty("role", "ghost")
        self.reveal_button.setToolTip("Show the file in Finder")
        self.reveal_button.clicked.connect(self.reveal)
        title_row.addWidget(self.open_button)
        title_row.addWidget(self.reveal_button)
        layout.addLayout(title_row)

        # -- tags as chips, the note behind a link
        self.tags = TagChips()
        self.tags.tags_changed.connect(self._save_tag_list)
        self.tags.note_toggled.connect(self._show_note_editor)
        layout.addWidget(self.tags)
        self.note_box = QWidget()
        note_row = QHBoxLayout(self.note_box)
        note_row.setContentsMargins(0, 0, 0, 0)
        note_row.setSpacing(8)
        self.notes_edit = QPlainTextEdit()
        self.notes_edit.setPlaceholderText(
            "Notes for future you… (saved beside the library; the file is never changed)"
        )
        self.notes_edit.setFixedHeight(64)
        self.save_button = QPushButton("Save note")
        self.save_button.clicked.connect(self.save_note)
        note_row.addWidget(self.notes_edit, 1)
        note_row.addWidget(self.save_button, 0, Qt.AlignmentFlag.AlignTop)
        self.note_box.hide()
        layout.addWidget(self.note_box)

        # -- what to do with it
        self.use_bar = UseBar()
        self.use_bar.open_requested.connect(self.open_externally)
        self.set_theme(theme)
        layout.addWidget(self.use_bar)

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
            "the index, and it is not offered to a tool or for class. Exclude the folder in "
            "Settings, or keep such files out of the resources folder."
        )
        self.withheld_banner.setProperty("role", "danger")
        self.withheld_banner.setWordWrap(True)
        self.withheld_banner.hide()
        layout.addWidget(self.withheld_banner)

        # -- the file itself, filling the rest
        self.content_host = QWidget()
        self.content = QStackedLayout(self.content_host)

        # The tools' numbered, highlighted code view: the lines are numbered
        # as on the sheets Parsons or Trace will print from this file.
        self.code = CodeViewWidget()
        self.content.addWidget(self.code)

        self.text = QPlainTextEdit()
        self.text.setObjectName("TextView")
        self.text.setReadOnly(True)
        self.content.addWidget(self.text)

        self.image = ImageViewWidget()
        self.content.addWidget(self.image)

        # Files the library never opens: what it is and why, over an empty
        # frame. The use bar above carries Open externally as the main action.
        self.card = QFrame()
        self.card.setObjectName("ExternalCard")
        self.card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(10)
        card_layout.addStretch(1)
        self.card_title = make_label("", "section")
        self.card_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.card_text = make_label("", "muted", wrap=True)
        self.card_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self.card_title)
        card_layout.addWidget(self.card_text)
        card_layout.addStretch(2)
        self.content.addWidget(self.card)
        layout.addWidget(self.content_host, 1)

    # -- theming ---------------------------------------------------------
    def set_theme(self, theme: str) -> None:
        # The code view takes its colours from the stylesheet.
        self.use_bar.set_theme("light" if theme == "light" else "dark")

    # -- showing ---------------------------------------------------------
    def clear(self) -> None:
        self.resource = None
        self.stack.setCurrentWidget(self.empty)

    def show_resource(self, resource: Resource) -> None:
        self.resource = resource
        path = self.service.absolute(resource.rel_path)
        self.title.setText(resource.name)
        self.meta.setText(meta_line(resource))
        self.meta.setToolTip(f"{resource.rel_path}\n{KIND_LABEL.get(resource.kind, 'File')}")
        self.cloud_banner.setVisible(resource.cloud_only)
        self.withheld_banner.setVisible(resource.text_withheld)
        self.stack.setCurrentIndex(1)

        entry = self.service.tag_entry(resource.rel_path)
        self.tags.set_tags(entry.tags)
        self.tags.set_note(entry.notes)
        self.notes_edit.setPlainText(entry.notes)
        self.tags.note_link.setChecked(False)

        self.use_bar.show_for(resource)
        # One main action: when the use bar's is Open externally, the quiet
        # copy beside the title would only repeat it.
        self.open_button.setVisible(not self.use_bar.open_button.isVisibleTo(self.use_bar))

        if resource.cloud_only or resource.external_only:
            self._show_card(resource, path)
        elif resource.kind == "image":
            self.image.set_image(path)
            self.content.setCurrentWidget(self.image)
        elif resource.kind == "pdf":
            self._show_text(self._safe(lambda: read_pdf_text(path, page_cap=1), path), pdf=True)
        elif resource.kind == "python":
            self.code.set_text(self._safe(lambda: read_text(path), path))
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
                f"Open externally opens {path.name} in {app or 'its native app'}."
            )
        else:
            kind = KIND_LABEL.get(resource.kind, "this kind").lower()
            text = f"No preview for {kind} files. Open externally opens it in its native app."
        self.card_text.setText(text)
        self.content.setCurrentWidget(self.card)

    # -- actions ---------------------------------------------------------
    def open_externally(self) -> None:
        if self.resource:
            self.service.open_externally(self.service.absolute(self.resource.rel_path))

    def reveal(self) -> None:
        if self.resource:
            self.service.reveal(self.service.absolute(self.resource.rel_path))

    def _show_note_editor(self, show: bool) -> None:
        self.note_box.setVisible(show)
        if show:
            self.notes_edit.setFocus()

    def _save(self, tags: list[str], notes: str) -> None:
        if not self.resource:
            return
        entry = self.service.set_tags(self.resource.rel_path, tags, notes)
        self.tags.set_tags(entry.tags)
        self.tags.set_note(entry.notes)
        self.tags_saved.emit(self.resource.rel_path)

    def _save_tag_list(self, tags: list[str]) -> None:
        if self.resource:
            notes = self.service.tag_entry(self.resource.rel_path).notes
            self._save(tags, notes)

    def save_note(self) -> None:
        if self.resource:
            tags = self.service.tag_entry(self.resource.rel_path).tags
            self._save(tags, self.notes_edit.toPlainText())
            self.tags.note_link.setChecked(False)


def meta_line(resource: Resource) -> str:
    """``Python/Year 9 · 345 B · 9 Oct 2026``: the folder, size and date."""
    folder = resource.rel_path.rpartition("/")[0] or "Top folder"
    modified = datetime.fromtimestamp(resource.mtime)
    return f"{folder}  ·  {human_size(resource.size)}  ·  {modified.day} {modified:%b %Y}"
