"""A row of headline tiles (:class:`~staffroom.core.panel.StatTiles`): a small
capitalised label, the number large, a detail line under it. The one tile
marked ``action`` (the one that asks the teacher to act) takes the accent colour."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from staffroom.core.panel import Stat
from staffroom.shell.widgets.card import make_label
from staffroom.shell.widgets.elided_label import ElidedLabel


class StatTile(QFrame):
    def __init__(self, stat: Stat, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatTile")
        # Equal widths whatever the text; every tile takes the tallest one's height.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 10)
        layout.setSpacing(2)
        self.label = make_label(stat.label.upper(), "eyebrow")
        self.label.setToolTip(stat.label)
        # A long value (five questions to reteach) wraps once, then is cut with …;
        # the tooltip has it whole.
        self.value = ElidedLabel(stat.value, max_lines=2)
        self.value.setProperty("role", "stat-value")
        self.value.setProperty("action", stat.action)
        self.detail = ElidedLabel(stat.detail, max_lines=2)
        self.detail.setProperty("role", "faint")
        self.detail.setVisible(bool(stat.detail))
        layout.addWidget(self.label)
        layout.addWidget(self.value)
        layout.addWidget(self.detail)
        layout.addStretch(1)


class StatTilesWidget(QWidget):
    """Equal-width tiles in one row; ``set_stats`` replaces them."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatTiles")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.tiles: list[StatTile] = []
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

    def set_stats(self, stats: list[Stat]) -> None:
        for tile in self.tiles:
            self._layout.removeWidget(tile)
            tile.deleteLater()
        self.tiles = [StatTile(s) for s in stats]
        for tile in self.tiles:
            self._layout.addWidget(tile, 1)

    def values(self) -> dict[str, str]:
        """Label -> value as shown, for tests and screen readers."""
        return {t.label.toolTip(): t.value.text() for t in self.tiles}
