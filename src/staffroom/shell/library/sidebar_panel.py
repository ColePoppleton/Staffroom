"""The Resources root in the sidebar: search box, filters and the tree."""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.library.model import KIND_BY_EXT, Resource
from staffroom.shell.library.tree import REL_PATH_ROLE, ResourceTreeModel

ALL_KINDS = ["all", *sorted(set(KIND_BY_EXT.values())), "other"]


class ResourcesPanel(QWidget):
    search_changed = Signal(str)
    kind_changed = Signal(str)
    show_hidden_toggled = Signal(bool)
    resource_selected = Signal(str)
    reindex_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 8)
        layout.setSpacing(8)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search names and text…  (⌘K)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self.search)

        filters = QHBoxLayout()
        filters.setSpacing(6)
        self.kind = QComboBox()
        for k in ALL_KINDS:
            self.kind.addItem("All types" if k == "all" else k, k)
        self.kind.currentIndexChanged.connect(
            lambda i: self.kind_changed.emit(str(self.kind.itemData(i)))
        )
        self.hidden = QPushButton("Hidden")
        self.hidden.setProperty("role", "ghost")
        self.hidden.setCheckable(True)
        self.hidden.setToolTip("Show .DS_Store, __pycache__, zips and other cruft")
        self.hidden.toggled.connect(self.show_hidden_toggled.emit)
        filters.addWidget(self.kind, 1)
        filters.addWidget(self.hidden)
        layout.addLayout(filters)

        self.model = ResourceTreeModel()
        self.tree = QTreeView()
        self.tree.setObjectName("ResourceTree")
        self.tree.setModel(self.model)
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tree.selectionModel().currentChanged.connect(self._on_current)
        layout.addWidget(self.tree, 1)

        footer = QHBoxLayout()
        self.status = QLabel("")
        self.status.setProperty("role", "faint")
        self.reindex = QPushButton("Re-index")
        self.reindex.setProperty("role", "ghost")
        self.reindex.clicked.connect(self.reindex_requested.emit)
        footer.addWidget(self.status, 1)
        footer.addWidget(self.reindex)
        layout.addLayout(footer)

    def set_resources(self, resources: list[Resource], status: str, detail: str = "") -> None:
        """``detail`` is the longer explanation behind a terse status (shown as
        a tooltip), e.g. why some files are indexed by name only."""
        current = self.current_rel_path()
        self.model.set_resources(resources)
        self.status.setText(status)
        self.status.setToolTip(detail)
        self.tree.expandToDepth(0)
        if current:
            self.select(current)

    def set_indexing(self, running: bool, text: str = "") -> None:
        self.reindex.setEnabled(not running)
        if text:
            self.status.setText(text)

    def current_rel_path(self) -> str | None:
        index = self.tree.currentIndex()
        if not index.isValid():
            return None
        rel = index.data(REL_PATH_ROLE)
        return str(rel) if rel else None

    def select(self, rel_path: str) -> None:
        matches = self.model.match(
            self.model.index(0, 0),
            REL_PATH_ROLE,
            rel_path,
            1,
            Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
        )
        if matches:
            self.tree.setCurrentIndex(matches[0])
            self.tree.scrollTo(matches[0])

    def _on_current(self, current: QModelIndex, _previous: QModelIndex) -> None:
        rel = current.data(REL_PATH_ROLE) if current.isValid() else None
        if rel:
            self.resource_selected.emit(str(rel))
