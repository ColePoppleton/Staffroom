"""File and folder pickers. The shell owns the dialogs; tools only declare them."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget

from teaching_tools.core.panel import FilePicker, FolderPicker


class PathPickerWidget(QWidget):
    """A line edit plus a Browse button. ``changed`` fires with the new Path or
    None whenever the value changes, from the dialog or by typing."""

    changed = Signal(object)

    def __init__(self, spec: FilePicker | FolderPicker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self._last_dir = str(Path.home())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.edit = QLineEdit()
        placeholder = "Choose a folder…" if isinstance(spec, FolderPicker) else "Choose a file…"
        self.edit.setPlaceholderText(placeholder)
        self.edit.setClearButtonEnabled(True)
        self.edit.editingFinished.connect(self._emit)
        self.edit.textChanged.connect(self._on_text_changed)
        self.button = QPushButton("Browse…")
        self.button.clicked.connect(self.browse)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)

    # -- value ---------------------------------------------------------
    def value(self) -> Path | None:
        text = self.edit.text().strip()
        return Path(text).expanduser() if text else None

    def set_path(self, path: Path | None) -> None:
        self.edit.setText(str(path) if path else "")
        self._emit()

    # -- dialogs -------------------------------------------------------
    def browse(self) -> None:
        if isinstance(self.spec, FolderPicker):
            chosen = QFileDialog.getExistingDirectory(self, self.spec.label, self._last_dir)
        elif self.spec.mode == "save":
            chosen, _ = QFileDialog.getSaveFileName(
                self, self.spec.label, self._last_dir, ";;".join(self.spec.filters)
            )
        else:
            chosen, _ = QFileDialog.getOpenFileName(
                self, self.spec.label, self._last_dir, ";;".join(self.spec.filters)
            )
        if chosen:
            self._last_dir = str(Path(chosen).parent)
            self.set_path(Path(chosen))

    def _on_text_changed(self, text: str) -> None:
        if not text:
            self._emit()

    def _emit(self) -> None:
        self.changed.emit(self.value())
