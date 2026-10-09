"""The compact form of a :class:`~staffroom.core.panel.TablePreview`: a few
lines saying what was loaded (from the spec's ``summary``), under the file
picker, and a *Preview rows* link that opens the rows in a window on demand,
instead of an eleven-row table in the inputs pane."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from staffroom.core.log import get_logger
from staffroom.core.panel import Note, TablePreview
from staffroom.core.table import Table
from staffroom.shell.widgets.card import make_label
from staffroom.shell.widgets.table_view import TablePreviewWidget

log = get_logger(__name__)
TICK, WARN = "✓", "!"


def default_summary(table: Table) -> list[Note]:
    rows, cols = table.shape
    notes = [Note(f"{rows} rows × {cols} columns")]
    if table.dropped_columns:
        notes.append(Note("Identifier columns dropped: " + ", ".join(table.dropped_columns)))
    return notes


class LoadSummaryWidget(QWidget):
    def __init__(self, spec: TablePreview, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.table: Table | None = None
        self.lines: list[QLabel] = []
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        # Placed in the group's heading by the tool panel.
        self.preview_button = QPushButton("Preview rows")
        self.preview_button.setProperty("role", "link")
        self.preview_button.setToolTip(
            "Open the file's rows in a window (identifier columns dropped)"
        )
        self.preview_button.clicked.connect(self.open_preview)
        self.preview_button.setEnabled(False)
        self.dialog: QDialog | None = None
        self.setVisible(False)

    def notes(self) -> list[Note]:
        return [Note(label.text()[2:], label.property("role") == "note-ok") for label in self.lines]

    def _show(self, notes: list[Note]) -> None:
        for label in self.lines:
            self._layout.removeWidget(label)
            label.deleteLater()
        self.lines = []
        for note in notes:
            label = make_label(f"{TICK if note.ok else WARN} {note.text}", "", wrap=True)
            label.setProperty("role", "note-ok" if note.ok else "note-warn")
            self._layout.addWidget(label)
            self.lines.append(label)
        self.setVisible(bool(notes))

    def set_table(self, table: Table | None) -> None:
        self.table = table
        self.preview_button.setEnabled(table is not None and bool(table.columns))
        if table is None:
            self._show([])
            return
        summarise = self.spec.summary or default_summary
        try:
            notes = list(summarise(table))
        except Exception as exc:  # a summary must never stop a file loading
            log.warning("summary of %s failed: %s", self.spec.source, exc)
            notes = default_summary(table)
        self._show(notes)

    def set_error(self, message: str) -> None:
        self.table = None
        self.preview_button.setEnabled(False)
        self._show([Note(message, ok=False)])

    def open_preview(self) -> None:
        if self.table is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self.spec.label)
        dialog.resize(640, 460)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(make_label("Identifier columns are already dropped.", "faint"))
        preview = TablePreviewWidget(self.spec)
        preview.set_table(self.table)
        layout.addWidget(preview, 1)
        self.dialog = dialog
        dialog.show()
