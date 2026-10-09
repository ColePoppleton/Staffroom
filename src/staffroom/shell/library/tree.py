"""A folder tree built from the index (not the filesystem), so hidden and
cloud-only state come from the same source as search.

The tree is filled through the ``QAbstractItemModel`` API (``insertRow``,
``setData`` on a ``QModelIndex``) and never through ``QStandardItem``
objects. A ``QStandardItem`` reached from Python gets a shiboken wrapper
that the model's ``clear()`` or destruction does not invalidate (items are
not ``QObject``s), and ``appendRow`` links child and parent wrappers into a
reference cycle that only the garbage collector frees, at a time of its
choosing. Until then the wrappers are stale, and the next Qt object
allocated at one of those addresses comes back as the wrong Python type:
``'QStandardItem' object has no attribute 'selectionChanged'`` (#49).
``QModelIndex`` is a value type, so this file creates no wrapper to go stale."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtGui import QFont, QStandardItemModel

from staffroom.core.library.model import Resource

REL_PATH_ROLE = Qt.ItemDataRole.UserRole
KIND_ROLE = Qt.ItemDataRole.UserRole + 1

KIND_GLYPH = {
    "python": "py",
    "text": "txt",
    "markdown": "md",
    "csv": "csv",
    "pdf": "pdf",
    "image": "img",
    "office": "doc",
    "scratch": "sb",
    "audio": "aud",
    "video": "vid",
    "archive": "zip",
    "database": "db",
    "diagram": "dia",
    "other": "?",
}


@dataclass
class _Folder:
    """A folder of the resources root, assembled before anything touches Qt."""

    dirs: dict[str, _Folder] = field(default_factory=dict)
    files: list[Resource] = field(default_factory=list)

    def child(self, name: str) -> _Folder:
        return self.dirs.setdefault(name, _Folder())


class ResourceTreeModel(QStandardItemModel):
    def __init__(self) -> None:
        super().__init__()
        self.setHorizontalHeaderLabels(["Resources"])

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        """Nothing in the tree is editable (``QStandardItem`` defaults to editable)."""
        return super().flags(index) & ~Qt.ItemFlag.ItemIsEditable

    def set_resources(self, resources: Iterable[Resource]) -> None:
        self.clear()
        self.setHorizontalHeaderLabels(["Resources"])
        root = _Folder()
        for res in resources:
            folder = root
            parent_path, _, _name = res.rel_path.rpartition("/")
            for part in parent_path.split("/"):
                if part:
                    folder = folder.child(part)
            folder.files.append(res)
        self._fill(QModelIndex(), root)

    def _fill(self, parent: QModelIndex, folder: _Folder) -> None:
        """Folders first, then files, each sorted case-insensitively."""
        bold = QFont()
        bold.setWeight(QFont.Weight.DemiBold)
        for name in sorted(folder.dirs, key=str.lower):
            index = self._append(parent, name)
            self.setData(index, bold, Qt.ItemDataRole.FontRole)
            self._fill(index, folder.dirs[name])
        for res in sorted(folder.files, key=lambda r: r.name.lower()):
            index = self._append(parent, res.name + ("  ☁︎" if res.cloud_only else ""))
            self.setData(index, res.rel_path, REL_PATH_ROLE)
            self.setData(index, res.kind, KIND_ROLE)
            tip = f"{res.rel_path}\n{res.kind}"
            if res.cloud_only:
                tip += "\ncloud-only: not downloaded on this Mac"
            if res.hidden:
                tip += "\nhidden by default"
                italic = QFont()
                italic.setItalic(True)
                self.setData(index, italic, Qt.ItemDataRole.FontRole)
            self.setData(index, tip, Qt.ItemDataRole.ToolTipRole)

    def _append(self, parent: QModelIndex, text: str) -> QModelIndex:
        """Add a row under ``parent`` and return its index. A fresh child
        item has no columns yet, so the first row under it brings one."""
        if parent.isValid() and self.columnCount(parent) == 0:
            self.insertColumn(0, parent)
        row = self.rowCount(parent)
        self.insertRow(row, parent)
        index = self.index(row, 0, parent)
        self.setData(index, text, Qt.ItemDataRole.DisplayRole)
        return index
