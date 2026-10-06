"""Pick a file from the Resource Library, or anywhere via a dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

from teaching_tools.core.library.service import ResourceService
from teaching_tools.core.panel import ResourcePicker


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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("Choose a resource from the library, or a file…")
        self.edit.setClearButtonEnabled(True)
        self.edit.editingFinished.connect(self._emit)
        self.library_button = QPushButton("From library…")
        self.library_button.setProperty("role", "primary")
        self.library_button.clicked.connect(self.pick_from_library)
        self.library_button.setEnabled(resources is not None)
        self.browse_button = QPushButton("Browse…")
        self.browse_button.clicked.connect(self.browse)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.library_button)
        layout.addWidget(self.browse_button)

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
        pattern = f"*{self.spec.filter_ext}" if self.spec.filter_ext else "*"
        chosen, _ = QFileDialog.getOpenFileName(self, self.spec.label, start, f"Files ({pattern})")
        if chosen:
            self.set_path(Path(chosen))

    def _emit(self) -> None:
        self.changed.emit(self.value())
