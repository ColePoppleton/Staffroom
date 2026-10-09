"""The program a code tool works on (:class:`~staffroom.core.panel.CodeSource`):
a source chip over a numbered, highlighted view of the code.

* No program yet: the chip offers *From library…* and *Browse…*.
* A file: the chip shows its type, name and folder (the library path when it
  is in the Resource Library; the full path in the tooltip) and *Change ▾*;
  the view shows the file, read-only, and follows it when it is saved again
  (Thonny is the editor; this only shows what it saved).
* *Paste instead* (the group's trailing link) empties the view and makes it
  editable for a paste; *Use a file* goes back to the file.

The value is a :class:`~staffroom.core.panel.CodeValue`. Text is only read
here for showing; :mod:`staffroom.core.codeinput` reads the file again for
the run.

:class:`LineLink` joins a results table whose rows carry line numbers to the
view: a selected row lights its line, a clicked line selects its rows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QFileSystemWatcher,
    QItemSelection,
    QItemSelectionModel,
    QObject,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.library.service import ResourceService
from staffroom.core.panel import CodeSource, CodeValue
from staffroom.shell.widgets.choice import ChoiceWidget
from staffroom.shell.widgets.code_view import CodeViewWidget
from staffroom.shell.widgets.elided_label import ElidedLabel
from staffroom.shell.widgets.table_view import TableWidget

MIN_LINES, MAX_LINES = 6, 24  # the view fits the program between these, then scrolls
PASTE_LINES = 14
MAX_SHOWN_BYTES = 512 * 1024  # bigger files are named, not shown
PASTE_INSTEAD, USE_A_FILE = "Paste instead", "Use a file"


def _read_for_view(path: Path) -> tuple[str | None, str]:
    """``(text, problem)``: the file's text to show, or why it is not shown."""
    try:
        if path.stat().st_size > MAX_SHOWN_BYTES:
            return None, f"{path.name} is too large to show here."
        data = path.read_bytes()
    except FileNotFoundError:
        return None, f"Could not find {path.name} (looked in {path.parent})."
    except OSError as exc:
        return None, f"Could not read {path.name}: {exc.strerror or exc.__class__.__name__}."
    try:
        return data.decode("utf-8"), ""
    except UnicodeDecodeError:
        return None, f"{path.name} is not a text file."


class CodeSourceWidget(QWidget):
    changed = Signal(object)  # the new CodeValue

    def __init__(
        self,
        spec: CodeSource,
        resources: ResourceService | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.resources = resources
        self._path: Path | None = None
        self._pasting = False
        self._pasted = ""  # kept while a file is shown, for going back to the paste
        self._problem = ""
        self._last_dir = str(Path.home())
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._file_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # The trailing link of the group heading (the panel places it).
        self.mode_link = QPushButton(PASTE_INSTEAD)
        self.mode_link.setProperty("role", "link")
        self.mode_link.setToolTip("Paste a program instead of choosing a file")
        self.mode_link.clicked.connect(self.toggle_paste)

        layout.addWidget(self._build_chip())

        self.choice: ChoiceWidget | None = None
        if spec.choice is not None:
            row = QHBoxLayout()
            row.setSpacing(10)
            label = QLabel(spec.choice.label)
            label.setProperty("role", "muted")
            self.choice = ChoiceWidget(spec.choice)
            row.addWidget(label)
            row.addWidget(self.choice)
            row.addStretch(1)
            layout.addLayout(row)

        self.view = CodeViewWidget(read_only=True)
        self.view.textChanged.connect(self._text_edited)
        layout.addWidget(self.view)
        self._show()

    # -- the chip ----------------------------------------------------------
    def _build_chip(self) -> QFrame:
        chip = QFrame()
        chip.setObjectName("FileChip")
        row = QHBoxLayout(chip)
        row.setContentsMargins(8, 5, 6, 5)
        row.setSpacing(8)
        self.badge = QLabel("PY")
        self.badge.setObjectName("FileBadge")
        self.name = QLabel("")
        self.name.setObjectName("FileName")
        self.folder = ElidedLabel("")
        self.folder.setProperty("role", "faint")
        self.library_button = QPushButton("From library…")
        self.library_button.clicked.connect(self.pick_from_library)
        self.library_button.setEnabled(self.resources is not None)
        self.browse_button = QPushButton("Browse…")
        self.browse_button.clicked.connect(self.browse)
        self.change = QPushButton("Change ▾")
        self.change.setObjectName("CodeChange")  # the ▾ is in the text: no menu arrow
        self.change.setProperty("role", "ghost")
        self.change.setToolTip("Choose a different program")
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
        self.chip = chip
        return chip

    # -- value -------------------------------------------------------------
    def value(self) -> CodeValue:
        if self._pasting:
            return CodeValue(None, self.view.toPlainText())
        return CodeValue(self._path, self.view.toPlainText() if self._path else "")

    @property
    def pasting(self) -> bool:
        return self._pasting

    def set_path(self, path: Path | None) -> None:
        """Show this file (None: no program); leaves paste mode."""
        if self._pasting:
            self._pasted = self.view.toPlainText()
        self._pasting = False
        self._watch(path)
        self._path = path
        self._load()
        self._show()
        self._emit()

    def set_pasted(self, text: str) -> None:
        """Paste mode with ``text`` in the view."""
        self._pasting = True
        self._watch(None)
        self._problem = ""
        self._show()
        self.view.blockSignals(True)
        self.view.set_text(text)
        self.view.blockSignals(False)
        self._emit()

    def toggle_paste(self) -> None:
        if self._pasting:
            self._pasted = self.view.toPlainText()
            self.set_path(self._path)
        else:
            self.set_pasted(self._pasted)
            self.view.setFocus()

    def reload(self) -> None:
        """Show the file as it is on disk now (it may have been saved since)."""
        if not self._pasting and self._path is not None:
            self._load()
            self._show()

    # -- dialogs -------------------------------------------------------------
    def pick_from_library(self) -> None:
        if self.resources is None:
            return
        chosen = self.resources.pick(self.spec.filter_ext)
        if chosen:
            self.set_path(chosen)

    def browse(self) -> None:
        start = str(self._path.parent) if self._path else self._last_dir
        pattern = f"*{self.spec.filter_ext}" if self.spec.filter_ext else "*"
        chosen, _ = QFileDialog.getOpenFileName(self, self.spec.label, start, f"Files ({pattern})")
        if chosen:
            self._last_dir = str(Path(chosen).parent)
            self.set_path(Path(chosen))

    # -- internals -------------------------------------------------------------
    def _watch(self, path: Path | None) -> None:
        if self.watcher.files():
            self.watcher.removePaths(self.watcher.files())
        if path is not None and path.exists():
            self.watcher.addPath(str(path))

    def _file_changed(self, name: str) -> None:
        # Editors often save by replacing the file, which drops the watch.
        if self._path is not None and Path(name) == self._path:
            self._watch(self._path)
            self.reload()
            self._emit()

    def _load(self) -> None:
        text, self._problem = (None, "") if self._path is None else _read_for_view(self._path)
        self.view.blockSignals(True)
        self.view.set_text(text or "")
        self.view.blockSignals(False)

    def _display(self, path: Path) -> tuple[str, str]:
        """``(name, folder)``: the folder relative to the library root for a
        library file (``Python/Year 9``), else the parent folder's name (the
        full path is the chip's tooltip)."""
        if self.resources is not None:
            try:
                rel = path.resolve().relative_to(self.resources.root.resolve())
                return path.name, rel.parent.as_posix() if rel.parent != Path(".") else ""
            except (ValueError, OSError):
                pass
        return path.name, path.parent.name

    def _show(self) -> None:
        pasting, path = self._pasting, self._path
        has_file = path is not None and not pasting
        self.mode_link.setText(USE_A_FILE if pasting else PASTE_INSTEAD)
        self.mode_link.setToolTip(
            "Go back to the chosen file" if pasting else "Paste a program instead of a file"
        )
        self.badge.setVisible(has_file or pasting)
        self.name.setVisible(has_file or pasting)
        self.change.setVisible(has_file)
        self.library_button.setVisible(not has_file and not pasting)
        self.browse_button.setVisible(not has_file and not pasting)
        self.folder.setVisible(True)
        if pasting:
            self.badge.setText("TXT")
            self.name.setText("Pasted code")
            self.folder.setText("not saved anywhere")
            self.chip.setToolTip("")
        elif path is not None:
            name, folder = self._display(path)
            self.badge.setText((path.suffix.lstrip(".") or "file").upper()[:4])
            self.name.setText(name)
            self.folder.setText(folder)
            self.chip.setToolTip(str(path))
        else:
            self.folder.setText("No program yet")
            self.chip.setToolTip("")
        self.view.setReadOnly(not pasting)
        if pasting:
            self.view.setPlaceholderText("Paste a program here…")
        elif self._problem:
            self.view.setPlaceholderText(self._problem)
        else:
            self.view.setPlaceholderText(
                "The program shows here once you choose it, or paste one instead."
            )
        if pasting:
            self.view.fit_height(PASTE_LINES, PASTE_LINES)
        elif has_file and not self._problem:
            self.view.fit_height(MIN_LINES, MAX_LINES)
        else:
            self.view.fit_height(3, 3)

    def _text_edited(self) -> None:
        if self._pasting:
            self._emit()

    def _emit(self) -> None:
        self.changed.emit(self.value())


def _line_of(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class LineLink(QObject):
    """Rows of ``table`` point at lines of ``code`` through ``column``: a
    selected row lights its line; a clicked line selects every row that
    points at it and scrolls to the first."""

    def __init__(self, table: TableWidget, column: str, code: CodeViewWidget) -> None:
        super().__init__(table)
        self.table = table
        self.column = column
        self.code = code
        self._syncing = False
        selection = table.selectionModel()
        selection.selectionChanged.connect(self._rows_selected)
        code.line_clicked.connect(self.select_line)

    def _column_index(self) -> int | None:
        model = self.table.model()
        horizontal = Qt.Orientation.Horizontal
        for col in range(model.columnCount()):
            if model.headerData(col, horizontal) == self.column:
                return col
        return None

    def line_of_row(self, row: int, col: int | None = None) -> int | None:
        col = self._column_index() if col is None else col
        if col is None:
            return None
        return _line_of(self.table.model().index(row, col).data())

    def _rows_selected(self, *_: object) -> None:
        if self._syncing:
            return
        col = self._column_index()
        rows = sorted({i.row() for i in self.table.selectionModel().selectedIndexes()})
        lines = [n for n in (self.line_of_row(r, col) for r in rows) if n is not None]
        self.code.highlight_lines(lines)

    def select_line(self, line: int) -> None:
        """Select the rows whose line is ``line`` (none: clear the selection)."""
        model = self.table.model()
        col = self._column_index()
        rows = [r for r in range(model.rowCount()) if self.line_of_row(r, col) == line]
        selection = QItemSelection()
        last = model.columnCount() - 1
        for r in rows:
            selection.select(model.index(r, 0), model.index(r, last))
        self._syncing = True
        try:
            flags = QItemSelectionModel.SelectionFlag.ClearAndSelect
            self.table.selectionModel().select(selection, flags)
        finally:
            self._syncing = False
        self.code.highlight_lines([line] if rows else [], scroll=False)
        if rows:
            self.table.scrollTo(model.index(rows[0], 0))
