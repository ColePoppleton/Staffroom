"""The Library's "Tags ▾" filter (#111): a button beside the type filter
whose menu lists the tags in use, each with how many files carry it.
Choosing a tag narrows the tree and the search results to files carrying
it; choosing more narrows further (every chosen tag is required).

The tags come from the library's sidecar; this widget only shows counts and
remembers the choice. It never writes anything."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QPushButton, QWidget

from staffroom.core.library.tags import TagCount, normalise_tags

EMPTY_HINT = "No tags yet: add one under a file's title"
BUTTON_TAG_CHARS = 12  # a long tag is cut short on the button, whole in the menu


def button_text(chosen: list[str]) -> str:
    """``Tags ▾``, ``loops ▾``, ``loops +1 ▾``."""
    if not chosen:
        return "Tags ▾"
    first = chosen[0]
    if len(first) > BUTTON_TAG_CHARS:
        first = first[: BUTTON_TAG_CHARS - 1] + "…"
    more = f" +{len(chosen) - 1}" if len(chosen) > 1 else ""
    return f"{first}{more} ▾"


class TagFilterButton(QPushButton):
    tags_changed = Signal(list)  # list[str], the chosen tags

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(button_text([]), parent)
        self.setObjectName("TagFilter")
        self._counts: list[TagCount] = []
        self._chosen: list[str] = []
        self.menu_ = QMenu(self)
        self.menu_.setObjectName("TagFilterMenu")
        # The entries are built as the menu opens, never while one of them
        # is still emitting ``triggered``.
        self.menu_.aboutToShow.connect(self._fill_menu)
        self.setMenu(self.menu_)
        self._rebuild()

    # -- state -------------------------------------------------------------
    def chosen(self) -> list[str]:
        return list(self._chosen)

    def counts(self) -> list[TagCount]:
        return list(self._counts)

    def set_counts(self, counts: list[TagCount]) -> None:
        """The tags in use now. A chosen tag no file carries any more is
        dropped quietly (the caller is already refreshing), so the filter
        never hides everything behind a tag the menu no longer offers."""
        self._counts = list(counts)
        in_use = {c.tag for c in counts}
        self._chosen = [t for t in self._chosen if t in in_use]
        self._rebuild()

    def set_chosen(self, tags: list[str]) -> None:
        chosen = normalise_tags(tags)
        if chosen == self._chosen:
            return
        self._chosen = chosen
        self._rebuild()
        self.tags_changed.emit(self.chosen())

    def toggle_tag(self, tag: str) -> None:
        if tag in self._chosen:
            self.set_chosen([t for t in self._chosen if t != tag])
        else:
            self.set_chosen([*self._chosen, tag])

    def clear(self) -> None:
        self.set_chosen([])

    # -- the button and its menu -------------------------------------------
    def _rebuild(self) -> None:
        self.setText(button_text(self._chosen))
        self.setProperty("active", "true" if self._chosen else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        if self._chosen:
            self.setToolTip("Showing files tagged " + " and ".join(self._chosen))
        else:
            self.setToolTip("Show only files with a tag")

    def _fill_menu(self) -> None:
        menu = self.menu_
        menu.clear()
        if not self._counts:
            hint = QAction(EMPTY_HINT, menu)
            hint.setEnabled(False)
            menu.addAction(hint)
            return
        for count in self._counts:
            action = QAction(count.label, menu)
            action.setCheckable(True)
            action.setChecked(count.tag in self._chosen)
            action.setData(count.tag)
            action.triggered.connect(lambda _on=False, t=count.tag: self.toggle_tag(t))
            menu.addAction(action)
        if self._chosen:
            menu.addSeparator()
            clear = QAction("Show all files", menu)
            clear.triggered.connect(self.clear)
            menu.addAction(clear)

    def tag_actions(self) -> list[QAction]:
        """The menu's tag entries as it would open now (tests, screenshots)."""
        self._fill_menu()
        return [a for a in self.menu_.actions() if a.data()]
