"""Pick a file from the Resource Library, or anywhere via a dialog.

A path field over *From library…* and *Browse…*; or, for a
:class:`~staffroom.core.panel.ResourcePicker` with ``chip``, a chip like a
code tool's: before a file, *From library…* and *Browse…*; with one, its
type, name and folder (the library folder for a library file, the full path
in the tooltip) and *Change ▾*."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.library.service import ResourceService
from staffroom.core.panel import ResourcePicker
from staffroom.shell.widgets.elided_label import ElidedLabel


class ResourcePickerWidget(QWidget):
    changed = Signal(object)

    def __init__(
        self,
        spec: ResourcePicker,
        resources: ResourceService | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.resources = resources
        # Two rows, so the path keeps the inputs pane's full width: the field,
        # then the two ways to fill it. The pane's one primary button is Run.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Choose a resource from the library, or a file…")
        self.edit.setClearButtonEnabled(True)
        self.edit.editingFinished.connect(self._emit)
        self.library_button = QPushButton("From library…")
        self.library_button.clicked.connect(self.pick_from_library)
        self.library_button.setEnabled(resources is not None)
        self.browse_button = QPushButton("Browse…")
        self.browse_button.clicked.connect(self.browse)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self.library_button)
        buttons.addWidget(self.browse_button)
        buttons.addStretch(1)
        layout.addWidget(self.edit)
        layout.addLayout(buttons)
        self.chip: QFrame | None = None
        if spec.chip:
            self._build_chip(layout, buttons)

    def _build_chip(self, layout: QVBoxLayout, buttons: QHBoxLayout) -> None:
        """The chip replaces the field and the button row; the field still
        holds the value."""
        self.edit.hide()
        for button in (self.library_button, self.browse_button):
            buttons.removeWidget(button)
        layout.removeItem(buttons)
        chip = QFrame()
        chip.setObjectName("FileChip")
        row = QHBoxLayout(chip)
        row.setContentsMargins(8, 5, 6, 5)
        row.setSpacing(8)
        self.badge = QLabel("")
        self.badge.setObjectName("FileBadge")
        self.name = QLabel("")
        self.name.setObjectName("FileName")
        self.folder = ElidedLabel("")
        self.folder.setProperty("role", "faint")
        self.change = QPushButton("Change ▾")
        self.change.setObjectName("CodeChange")  # the ▾ is in the text: no menu arrow
        self.change.setProperty("role", "ghost")
        self.change.setToolTip("Choose a different file")
        menu = QMenu(self.change)
        library = menu.addAction("From library…", self.pick_from_library)
        library.setEnabled(self.resources is not None)
        menu.addAction("Browse…", self.browse)
        self.change.setMenu(menu)
        row.addWidget(self.badge)
        row.addWidget(self.name)
        row.addWidget(self.folder, 1)
        row.addWidget(self.library_button)
        row.addWidget(self.browse_button)
        row.addWidget(self.change)
        layout.addWidget(chip)
        self.chip = chip
        self._show_chip()

    def _folder(self, path: Path) -> str:
        """The library folder of a library file (``Computing/Year 10``),
        else the parent folder's name."""
        if self.resources is not None:
            try:
                rel = path.resolve().relative_to(self.resources.root.resolve())
                return rel.parent.as_posix() if rel.parent != Path(".") else "Library"
            except (ValueError, OSError):
                pass
        return path.parent.name

    def _show_chip(self) -> None:
        if self.chip is None:
            return
        path = self.value()
        has_file = path is not None
        for widget in (self.badge, self.name, self.change):
            widget.setVisible(has_file)
        for widget in (self.library_button, self.browse_button):
            widget.setVisible(not has_file)
        if path is None:
            self.folder.setText("No file yet")
            self.chip.setToolTip("")
            return
        self.badge.setText((path.suffix.lstrip(".") or "file").upper()[:4])
        self.name.setText(path.name)
        self.folder.setText(self._folder(path))
        self.chip.setToolTip(str(path))

    def value(self) -> Path | None:
        """Absolute path. Text typed or shown relative to the library root is
        resolved against it."""
        text = self.edit.text().strip()
        if not text:
            return None
        path = Path(text).expanduser()
        if not path.is_absolute() and self.resources is not None:
            path = self.resources.root / path
        return path

    def set_path(self, path: Path | None) -> None:
        self.edit.setText(self._display(path) if path else "")
        self.edit.setToolTip(str(path) if path else "")
        self._show_chip()
        self._emit()

    def _display(self, path: Path) -> str:
        """Library files show as ``Python/OCR Booklet/9a.py``; others in full."""
        if self.resources is not None:
            try:
                return path.resolve().relative_to(self.resources.root.resolve()).as_posix()
            except (ValueError, OSError):
                pass
        return str(path)

    def pick_from_library(self) -> None:
        if self.resources is None:
            return
        chosen = self.resources.pick(self.spec.filter_ext)
        if chosen:
            self.set_path(chosen)

    def browse(self) -> None:
        current = self.value()
        start = str(current.parent) if current else str(Path.home())
        pattern = " ".join(f"*{ext}" for ext in self.spec.extensions) or "*"
        chosen, _ = QFileDialog.getOpenFileName(self, self.spec.label, start, f"Files ({pattern})")
        if chosen:
            self.set_path(Path(chosen))

    def _emit(self) -> None:
        self.changed.emit(self.value())
