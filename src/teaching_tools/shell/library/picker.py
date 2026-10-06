"""The library picker: how a tool asks the teacher for a resource.

A palette, not a file dialog: one big search field; the folder tree while
the field is empty, rich search results while typing; arrow keys and Enter
choose. Office and other files are listed too (a tool may want to open them
externally), cloud-only ones are not.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QModelIndex, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from teaching_tools.core.library.model import Resource, SearchHit
from teaching_tools.core.library.service import LibraryService
from teaching_tools.shell.library.result_item import add_result_row, no_matches_row
from teaching_tools.shell.library.tree import REL_PATH_ROLE, ResourceTreeModel

REL_ROLE = Qt.ItemDataRole.UserRole


class ResourcePickerDialog(QDialog):
    def __init__(
        self, service: LibraryService, filter_ext: str | None, parent: QWidget | None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("Palette")
        self.setWindowTitle("Choose a resource")
        self.setModal(True)
        self.resize(760, 580)
        self.service = service
        self.filter_ext = filter_ext.lower() if filter_ext else None
        self._chosen: Resource | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(10)

        self.search = QLineEdit()
        self.search.setObjectName("PaletteSearch")
        what = f"{self.filter_ext} files" if self.filter_ext else "the library"
        self.search.setPlaceholderText(f"Search {what} by name or contents…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.refresh)
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        hint = QLabel("↑ ↓ to move   ·   Enter to choose   ·   Esc to cancel")
        hint.setObjectName("PaletteHint")
        hint.setProperty("role", "faint")
        layout.addWidget(hint)

        self.stack = QStackedWidget()
        self.tree_model = ResourceTreeModel()
        self.tree = QTreeView()
        self.tree.setObjectName("ResourceTree")
        self.tree.setModel(self.tree_model)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(16)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.doubleClicked.connect(self._on_tree_double_click)
        self.tree.selectionModel().currentChanged.connect(self._on_tree_current)
        self.results = QListWidget()
        self.results.setObjectName("ResultList")
        self.results.itemDoubleClicked.connect(lambda _i: self._choose_current())
        self.results.currentItemChanged.connect(self._on_result_current)
        self.stack.addWidget(self.tree)
        self.stack.addWidget(self.results)
        layout.addWidget(self.stack, 1)

        footer = QHBoxLayout()
        footer.setSpacing(10)
        self.selected_label = QLabel("")
        self.selected_label.setProperty("role", "muted")
        self.selected_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        self.choose_button = QPushButton("Choose")
        self.choose_button.setProperty("role", "primary")
        self.choose_button.setEnabled(False)
        self.choose_button.clicked.connect(self._choose_current)
        footer.addWidget(self.selected_label, 1)
        footer.addWidget(cancel)
        footer.addWidget(self.choose_button)
        layout.addLayout(footer)

        self._resources = [
            r
            for r in service.resources()
            if not r.cloud_only and (self.filter_ext is None or r.ext == self.filter_ext)
        ]
        self.refresh("")
        self.search.setFocus()

    # -- population ------------------------------------------------------
    def _matches_filter(self, resource: Resource) -> bool:
        return not resource.cloud_only and (
            self.filter_ext is None or resource.ext == self.filter_ext
        )

    def refresh(self, text: str) -> None:
        text = text.strip()
        self._set_chosen(None)
        if not text:
            self.tree_model.set_resources(self._resources)
            self.tree.expandToDepth(0)
            self.stack.setCurrentWidget(self.tree)
            return
        self.results.clear()
        hits = [h for h in self.service.search(text) if self._matches_filter(h.resource)]
        seen = {h.resource.rel_path for h in hits}
        # Name-substring matches that FTS prefix matching missed (e.g. "loop" in "7_While_Loops").
        for r in self._resources:
            if r.rel_path not in seen and text.lower() in r.rel_path.lower():
                hits.append(SearchHit(r, "", 0.0))
        for hit in hits:
            add_result_row(self.results, hit, REL_ROLE)
        if not hits:
            no_matches_row(self.results)
        else:
            self.results.setCurrentRow(0)
        self.stack.setCurrentWidget(self.results)

    # -- selection -------------------------------------------------------
    def _set_chosen(self, resource: Resource | None) -> None:
        self._chosen = resource
        self.choose_button.setEnabled(resource is not None)
        self.selected_label.setText(resource.rel_path if resource else "")

    def _on_tree_current(self, current: QModelIndex, _previous: QModelIndex) -> None:
        rel = current.data(REL_PATH_ROLE) if current.isValid() else None
        self._set_chosen(self.service.get(str(rel)) if rel else None)

    def _on_tree_double_click(self, index: QModelIndex) -> None:
        if index.data(REL_PATH_ROLE):
            self._choose_current()

    def _on_result_current(self, current: QListWidgetItem | None) -> None:
        rel = current.data(REL_ROLE) if current else None
        self._set_chosen(self.service.get(str(rel)) if rel else None)

    def _choose_current(self) -> None:
        if self._chosen is not None:
            self.accept()

    def chosen(self) -> Path | None:
        return self.service.absolute(self._chosen.rel_path) if self._chosen else None

    # -- keyboard: arrows move the visible view, Enter chooses ------------
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.search and event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._choose_current()
                return True
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_PageUp, Qt.Key.Key_PageDown):
                view = self.stack.currentWidget()
                if isinstance(view, QTreeView | QListWidget):
                    view.keyPressEvent(event)
                return True
        return super().eventFilter(obj, event)


def pick_resource(
    service: LibraryService, filter_ext: str | None, parent: QWidget | None
) -> Path | None:
    dialog = ResourcePickerDialog(service, filter_ext, parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.chosen()
    return None
