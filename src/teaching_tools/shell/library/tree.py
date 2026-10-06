"""A folder tree built from the index (not the filesystem), so hidden and
cloud-only state come from the same source as search."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QStandardItem, QStandardItemModel

from teaching_tools.core.library.model import Resource

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


class ResourceTreeModel(QStandardItemModel):
    def __init__(self) -> None:
        super().__init__()
        self.setHorizontalHeaderLabels(["Resources"])

    def set_resources(self, resources: Iterable[Resource]) -> None:
        self.clear()
        self.setHorizontalHeaderLabels(["Resources"])
        root = self.invisibleRootItem()
        dirs: dict[str, QStandardItem] = {"": root}

        def dir_item(path: str) -> QStandardItem:
            if path in dirs:
                return dirs[path]
            parent_path, _, name = path.rpartition("/")
            parent = dir_item(parent_path)
            item = QStandardItem(name)
            item.setEditable(False)
            item.setData(None, REL_PATH_ROLE)
            font = item.font()
            font.setWeight(QFont.Weight.DemiBold)
            item.setFont(font)
            parent.appendRow(item)
            dirs[path] = item
            return item

        for res in sorted(resources, key=lambda r: r.rel_path.lower()):
            parent_path, _, _name = res.rel_path.rpartition("/")
            parent = dir_item(parent_path)
            label = res.name + ("  ☁︎" if res.cloud_only else "")
            item = QStandardItem(label)
            item.setEditable(False)
            item.setData(res.rel_path, REL_PATH_ROLE)
            item.setData(res.kind, KIND_ROLE)
            tip = f"{res.rel_path}\n{res.kind}"
            if res.cloud_only:
                tip += "\ncloud-only: not downloaded on this Mac"
            if res.hidden:
                tip += "\nhidden by default"
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
            item.setToolTip(tip)
            parent.appendRow(item)
        self._sort_dirs_first(root)

    def _sort_dirs_first(self, item: QStandardItem) -> None:
        rows = [item.takeRow(0) for _ in range(item.rowCount())]
        entries = [r[0] for r in rows]
        entries.sort(key=lambda it: (it.data(REL_PATH_ROLE) is not None, it.text().lower()))
        for it in entries:
            item.appendRow(it)
            if it.data(REL_PATH_ROLE) is None:
                self._sort_dirs_first(it)
