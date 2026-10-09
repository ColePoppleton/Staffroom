"""File and folder pickers. The shell owns the dialogs; tools only declare them."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from staffroom.core.panel import FilePicker, FolderPicker
from staffroom.shell.widgets.elided_label import ElidedLabel


class PathPickerWidget(QWidget):
    """A line edit plus a Browse button. ``changed`` fires with the new Path or
    None whenever the value changes, from the dialog or by typing.

    A :class:`FilePicker` with ``chip`` shows the chosen file as a chip
    instead: its type, its name (the full path in the tooltip) and *Change…*;
    before a file is chosen, one *Choose a file…* button."""

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
        self.chip: QFrame | None = None
        if isinstance(spec, FilePicker) and spec.chip:
            self._build_chip(layout)

    def _build_chip(self, layout: QHBoxLayout) -> None:
        self.edit.hide()  # still holds the value; the chip shows it
        self.button.setText("Choose a file…")
        chip = QFrame()
        chip.setObjectName("FileChip")
        row = QHBoxLayout(chip)
        row.setContentsMargins(8, 5, 6, 5)
        row.setSpacing(8)
        self.badge = QLabel("")
        self.badge.setObjectName("FileBadge")
        self.name = ElidedLabel("")
        self.name.setObjectName("FileName")
        self.change = QPushButton("Change…")
        self.change.setProperty("role", "link")
        self.change.setToolTip("Choose a different file")
        self.change.clicked.connect(self.browse)
        row.addWidget(self.badge)
        row.addWidget(self.name, 1)
        row.addWidget(self.change)
        layout.insertWidget(0, chip, 1)
        self.chip = chip
        self.edit.textChanged.connect(self._show_chip)
        self._show_chip()

    def _show_chip(self, *_: object) -> None:
        if self.chip is None:
            return
        path = self.value()
        self.chip.setVisible(path is not None)
        self.button.setVisible(path is None)
        if path is not None:
            self.badge.setText((path.suffix.lstrip(".") or "file").upper()[:4])
            self.name.setText(path.name)
            self.chip.setToolTip(str(path))

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
