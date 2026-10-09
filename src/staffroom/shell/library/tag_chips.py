"""A file's tags as chips under its title, added and removed in place, and
its note behind one link.

Tags and the note live in the library's sidecar file
(``.staffroom/tags.json``); the resource itself is never written. The row
emits what changed and the preview saves it through ``LibraryService``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from staffroom.shell.widgets.flow_layout import FlowLayout

NOTE_PREVIEW_CHARS = 60


class TagInput(QLineEdit):
    """The inline "+ tag" field: Enter adds, Esc (or leaving it empty) closes."""

    cancelled = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(event)
        if not self.text().strip():
            self.cancelled.emit()


class TagChip(QFrame):
    removed = Signal(str)

    def __init__(self, tag: str) -> None:
        super().__init__()
        self.tag = tag
        self.setObjectName("TagChip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 1, 3, 1)
        layout.setSpacing(2)
        text = QLabel(tag)
        text.setObjectName("TagText")
        self.remove = QPushButton("×")
        self.remove.setObjectName("TagRemove")
        self.remove.setToolTip(f"Remove the tag {tag}")
        self.remove.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove.clicked.connect(lambda: self.removed.emit(self.tag))
        layout.addWidget(text)
        layout.addWidget(self.remove)


class TagChips(QWidget):
    tags_changed = Signal(list)  # list[str], the whole new list
    note_toggled = Signal(bool)  # the note editor should show

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tags: list[str] = []
        self.chips: list[TagChip] = []
        self.layout_ = FlowLayout(self, spacing=6)

        self.add_button = QPushButton("+ tag")
        self.add_button.setObjectName("TagAdd")
        self.add_button.setToolTip("Tag this file (saved beside the library, never in the file)")
        self.add_button.clicked.connect(self.start_adding)
        self.input = TagInput()
        self.input.setObjectName("TagInput")
        self.input.setPlaceholderText("tag, then Enter")
        self.input.setFixedWidth(130)
        self.input.returnPressed.connect(self._commit)
        self.input.cancelled.connect(self._stop_adding)
        self.input.hide()
        self.note_link = QPushButton("")
        self.note_link.setObjectName("NoteLink")
        self.note_link.setCheckable(True)
        self.note_link.toggled.connect(self.note_toggled.emit)
        self._trailing: list[QWidget] = [self.add_button, self.input, self.note_link]
        for widget in self._trailing:
            self.layout_.addWidget(widget)
        # Many tags wrap onto another line; they never widen the window.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.set_note("")

    # -- state -------------------------------------------------------------
    def tags(self) -> list[str]:
        return list(self._tags)

    def set_tags(self, tags: list[str]) -> None:
        self._tags = list(tags)
        for chip in self.chips:
            self.layout_.removeWidget(chip)
            chip.deleteLater()
        for widget in self._trailing:
            self.layout_.removeWidget(widget)
        self.chips = []
        for tag in self._tags:
            chip = TagChip(tag)
            chip.removed.connect(self.remove_tag)
            self.layout_.addWidget(chip)
            self.chips.append(chip)
        for widget in self._trailing:
            self.layout_.addWidget(widget)

    def set_note(self, note: str) -> None:
        """The link shows the note's first line, or offers to add one."""
        first = note.strip().splitlines()[0] if note.strip() else ""
        if len(first) > NOTE_PREVIEW_CHARS:
            first = first[: NOTE_PREVIEW_CHARS - 1] + "…"
        self.note_link.setText(f"Note: {first}  ▸" if first else "+ note")
        self.note_link.setToolTip(note.strip() or "Add a note for future you")

    # -- editing -----------------------------------------------------------
    def start_adding(self) -> None:
        self.add_button.hide()
        self.input.show()
        self.input.setFocus()

    def _stop_adding(self) -> None:
        self.input.clear()
        self.input.hide()
        self.add_button.show()

    def _commit(self) -> None:
        added = [t.strip() for t in self.input.text().split(",") if t.strip()]
        self.input.clear()
        if added:
            self.tags_changed.emit(self._tags + [t for t in added if t not in self._tags])
        # Stay open for the next tag; Esc or an empty Enter closes.
        if not added:
            self._stop_adding()

    def add_tag(self, tag: str) -> None:
        self.input.setText(tag)
        self._commit()

    def remove_tag(self, tag: str) -> None:
        self.tags_changed.emit([t for t in self._tags if t != tag])
