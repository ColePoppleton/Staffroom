"""The result strip: one line on the output pane's top edge saying how the
last run went.

* **Before a run**: "Not run yet" and a chip that opens the folder the run
  will write to (the run button's foot names that folder).
* **Running**: the run's progress message.
* **After a run**: a tick, the outcome ("10 questions · seed 42", headline
  bold), one chip per file written and a ``Folder`` chip. A chip opens its
  file in the file's own app; right-click shows it in Finder. Warnings show as
  "3 warnings ▸", which opens the list under the line.
* **After a failure**: a cross and the message in the teacher's words; no
  chips.

Text wraps, and the strip grows to fit the lines it shows; a line is never
clipped (#121). An outcome wraps to two lines (the files are the chips); a
failure wraps to as many as it needs, up to :data:`FAILURE_LINES`, because
its last sentence is usually what to do. Past that, the text is cut between
words, never inside one; the full text is in the tooltip and in the run log
behind *Details*.
The strip only reports: what the chips do is the panel's job (it connects
``open_requested``, ``reveal_requested`` and ``folder_requested``).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.outcome import FileChip, file_chips, split_outcome, warning_count
from staffroom.core.plugin import RunResult
from staffroom.shell.widgets.elided_label import ElidedLabel

MAX_CHIPS = 5  # file chips shown at most; the rest (or what does not fit) under "+N more"
CHIP_LABEL_MAX = 26  # characters; longer labels are cut in the middle
HEADLINE_MAX = 40  # characters; a longer headline wraps with the rest instead
OUTCOME_LINES = 2  # an outcome, progress or "Not run yet": then cut, the rest in the tooltip
FAILURE_LINES = 6  # a failure is read to the end; only a runaway message is cut
IDLE_TEXT = "Not run yet"

ICONS = {"idle": "", "running": "…", "success": "✓", "danger": "✕"}


def _repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _short(label: str) -> str:
    if len(label) <= CHIP_LABEL_MAX:
        return label
    head = CHIP_LABEL_MAX // 2 - 1
    return f"{label[:head]}…{label[-(CHIP_LABEL_MAX - head - 1) :]}"


class Chip(QPushButton):
    """A pill button: an optional small kind tag (``PDF``) and a label."""

    def __init__(self, label: str, kind: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultChip")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(5)
        self.kind = QLabel(kind)
        self.kind.setObjectName("ChipKind")
        self.kind.setVisible(bool(kind))
        self.label = QLabel(_short(label))
        self.label.setObjectName("ChipLabel")
        for part in (self.kind, self.label):
            part.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(part)

    def text(self) -> str:  # what the chip says, for tests and accessibility
        kind = self.kind.text()
        return f"{kind} {self.label.text()}" if kind else self.label.text()

    def sizeHint(self) -> QSize:  # noqa: N802
        layout = self.layout()
        return layout.sizeHint() if layout is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()


class ResultStrip(QWidget):
    open_requested = Signal(object)  # Path: open in its app
    reveal_requested = Signal(object)  # Path: show in Finder
    folder_requested = Signal(object)  # Path: open the folder (creating it)

    def __init__(self, parent: QWidget | None = None, *, open_label: str = "Folder") -> None:
        super().__init__(parent)
        self.setObjectName("ResultStrip")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.state = "idle"
        self.open_label = open_label
        self.chips: list[Chip] = []  # one per file, in chip order; see shown_chips
        self.shown = 0  # how many of them are in the line
        self.files: list[FileChip] = []
        self.warnings: list[str] = []
        self._folder: Path | None = None
        self._next_folder: Path | None = None

        outer = self.outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 9, 20, 9)
        outer.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(10)
        outer.addLayout(row)

        self.icon = QLabel()
        self.icon.setObjectName("StripIcon")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setFixedSize(20, 20)
        row.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)

        # The headline (bold) and the rest (muted, wraps; see OUTCOME_LINES).
        self.headline = QLabel()
        self.headline.setObjectName("StripHeadline")
        self.headline.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        row.addWidget(self.headline, 0, Qt.AlignmentFlag.AlignTop)
        self.message = ElidedLabel(max_lines=OUTCOME_LINES, whole_words=True)
        self.message.setObjectName("StripMessage")
        row.addWidget(self.message, 1, Qt.AlignmentFlag.AlignTop)

        self.warning_toggle = QPushButton()
        self.warning_toggle.setObjectName("WarningToggle")
        self.warning_toggle.setCheckable(True)
        self.warning_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.warning_toggle.toggled.connect(self._show_warnings)
        row.addWidget(self.warning_toggle, 0, Qt.AlignmentFlag.AlignTop)

        # The chips sit at the end of the line while the outcome fits beside
        # them, and move to a line of their own under it when it does not.
        self.chips_box = QWidget()
        self.chips_box.setObjectName("StripChips")
        # Never sets the pane's minimum width: _place_chips shows only the
        # chips that fit the width the strip is given.
        self.chips_box.setMinimumWidth(1)
        box = QHBoxLayout(self.chips_box)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        self.chip_row = QHBoxLayout()
        self.chip_row.setSpacing(6)
        box.addLayout(self.chip_row)
        self.more = Chip("")
        self.more.setToolTip("More files from this run")
        self.more.clicked.connect(self._show_more)
        self.folder_chip = Chip(open_label)
        self.folder_chip.clicked.connect(self._open_folder)
        box.addWidget(self.more)
        box.addWidget(self.folder_chip)
        self.line = row
        self.line.addWidget(self.chips_box, 0, Qt.AlignmentFlag.AlignTop)
        self.second = QWidget()
        self.second_line = QHBoxLayout(self.second)
        self.second_line.setContentsMargins(30, 0, 0, 0)  # under the text, past the icon
        self.second_line.addStretch(1)
        self.second.hide()
        outer.addWidget(self.second)
        self.chips_wrapped = False

        self.warning_list = QLabel()
        self.warning_list.setObjectName("WarningList")
        self.warning_list.setWordWrap(True)
        self.warning_list.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        outer.addWidget(self.warning_list)

        self._show_idle()

    # -- reading (tests, accessibility) -----------------------------------
    def text(self) -> str:
        """The whole outcome or message, as set (not as cut to fit)."""
        rest = self.message.text()
        head = self.headline.text() if self.headline.isVisibleTo(self) else ""
        return " · ".join(p for p in (head, rest) if p)

    # -- states ------------------------------------------------------------
    def set_destination(self, folder: Path | None) -> None:
        """Where the next run will write. Before the first run the strip
        offers it as a chip; while a run is going its Folder chip opens it."""
        self._next_folder = folder
        if self.state == "idle":
            self._set_folder(folder, self.open_label)
            self._place_chips()

    def _show_idle(self) -> None:
        self._set_state("idle")
        self._set_text("", IDLE_TEXT, role="muted")
        self._set_chips([])
        self._set_folder(self._next_folder, self.open_label)
        self._set_warnings([])
        self._place_chips()

    def set_running(self, message: str = "Running…") -> None:
        self._set_state("running")
        self._set_text("", message or "Running…", role="muted")
        self._set_chips([])
        self._set_folder(self._next_folder, "Folder")  # still one click away
        self._set_warnings([])
        self._place_chips()

    def set_progress(self, message: str) -> None:
        if self.state == "running" and message:
            self._set_text("", message, role="muted")

    def add_warning(self, message: str) -> None:
        """A warning raised during the run; shown when the run ends."""
        self.warnings.append(message)

    def show_result(self, result: RunResult) -> None:
        self._set_state("success")
        head, rest = split_outcome(result.outcome)
        if result.outcome and rest and len(head) <= HEADLINE_MAX:
            self._set_text(head, rest, role="muted")
        else:
            self._set_text("", result.outcome or result.summary or "Done", role="outcome")
        self._set_chips(file_chips(result.files, result.labels))
        self._set_folder(result.files[0].parent if result.files else None, "Folder")
        self._set_warnings(self.warnings)
        self._place_chips()

    def show_failure(self, message: str) -> None:
        self._set_state("danger")
        self._set_text("", message, role="danger")
        self._set_chips([])
        self._set_folder(None)
        self._set_warnings(self.warnings)
        self._place_chips()

    # -- parts -------------------------------------------------------------
    def _set_state(self, state: str) -> None:
        self.state = state
        if state == "running":
            self.warnings = []
        self.icon.setText(ICONS[state])
        self.icon.setProperty("state", state)
        _repolish(self.icon)

    def _set_text(self, head: str, rest: str, *, role: str) -> None:
        self.headline.setText(head)
        self.headline.setVisible(bool(head))
        self.message.max_lines = FAILURE_LINES if role == "danger" else OUTCOME_LINES
        before = self.message.sizeHint().height()
        self.message.setText(rest)
        self.message.setProperty("role", role)
        _repolish(self.message)
        if self.message.sizeHint().height() != before:
            self._settle()

    def _settle(self) -> None:
        """Lay the strip and the panels around it out now, not on the next
        pass of the event loop, so no frame shows the new lines squeezed into
        the old height (half a line cut off top and bottom, #121)."""
        widget: QWidget | None = self
        while widget is not None and widget.isVisible():
            layout = widget.layout()
            if layout is not None:
                layout.activate()
            widget = widget.parentWidget()

    def _set_chips(self, files: list[FileChip]) -> None:
        for chip in self.chips:
            self.chip_row.removeWidget(chip)
            chip.deleteLater()
        self.files = files
        self.chips = []
        for item in files:
            chip = Chip(item.label, item.kind)
            chip.setToolTip(f"{item.path}\nClick to open · right-click to show in Finder")
            chip.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            chip.clicked.connect(lambda _c=False, p=item.path: self.open_requested.emit(p))
            chip.customContextMenuRequested.connect(
                lambda _pos, p=item.path: self.reveal_requested.emit(p)
            )
            self.chip_row.addWidget(chip, 0, Qt.AlignmentFlag.AlignTop)
            self.chips.append(chip)
        self._show_chips(min(len(files), MAX_CHIPS))

    @property
    def shown_chips(self) -> list[Chip]:
        return self.chips[: self.shown]

    def _show_chips(self, n: int) -> None:
        """The first ``n`` file chips in the line, the rest under "+N more"."""
        self.shown = n
        for i, chip in enumerate(self.chips):
            chip.setVisible(i < n)
        hidden = len(self.chips) - n
        self.more.label.setText(f"+{hidden} more")
        self.more.setVisible(hidden > 0)

    def _chips_width(self, n: int) -> int:
        """The chip box's width with ``n`` file chips shown."""
        spacing = 6
        widths = [c.sizeHint().width() for c in self.chips[:n]]
        if n < len(self.chips):
            widths.append(self.more.sizeHint().width() + 8)  # "+N more" with more digits
        if self._folder is not None:
            widths.append(self.folder_chip.sizeHint().width())
        return sum(widths) + spacing * max(len(widths) - 1, 0)

    def _set_folder(self, folder: Path | None, label: str = "Folder") -> None:
        self._folder = folder
        self.folder_chip.label.setText(label)
        self.folder_chip.setToolTip(str(folder) if folder else "")
        self.folder_chip.setVisible(folder is not None)

    def _set_warnings(self, warnings: list[str]) -> None:
        self.warning_toggle.setVisible(bool(warnings))
        self.warning_list.setText("\n".join(f"• {w}" for w in warnings))
        self._show_warnings(self.warning_toggle.isChecked())

    def _show_warnings(self, shown: bool) -> None:
        n = len(self.warnings) if self.warning_toggle.isVisible() else 0
        arrow = "▾" if shown else "▸"
        self.warning_toggle.setText(f"{warning_count(n)} {arrow}")
        self.warning_list.setVisible(shown and n > 0)

    # -- layout ------------------------------------------------------------
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_chips()

    def _text_width(self) -> int:
        """What the outcome needs on one line, plus the warnings toggle."""
        width = 0
        if self.headline.isVisibleTo(self):
            width += self.headline.fontMetrics().horizontalAdvance(self.headline.text()) + 12
        width += self.message.fontMetrics().horizontalAdvance(self.message.text()) + 8
        if self.warning_toggle.isVisibleTo(self):
            width += self.warning_toggle.sizeHint().width() + 10
        return width

    def _place_chips(self) -> None:
        """Chips at the end of the outcome's line when both fit; else on a
        line of their own. Either way, only as many file chips as fit."""
        margins = self.outer.contentsMargins()
        width = self.width() - margins.left() - margins.right() - self.icon.width() - 10
        most = min(len(self.chips), MAX_CHIPS)
        has_chips = self._folder is not None or bool(self.chips)
        wrap = has_chips and self._text_width() + 10 + self._chips_width(most) > width
        room = width if wrap else width - self._text_width() - 10
        n = most
        while n > 0 and self._chips_width(n) > room:
            n -= 1
        self._show_chips(n)
        if wrap == self.chips_wrapped:
            return
        self.chips_wrapped = wrap
        if wrap:
            self.line.removeWidget(self.chips_box)
            self.second_line.insertWidget(0, self.chips_box)
        else:
            self.second_line.removeWidget(self.chips_box)
            self.line.addWidget(self.chips_box, 0, Qt.AlignmentFlag.AlignTop)
        self.second.setVisible(wrap)

    # -- actions -----------------------------------------------------------
    def _open_folder(self) -> None:
        if self._folder is not None:
            self.folder_requested.emit(self._folder)

    def _show_more(self) -> None:
        menu = QMenu(self)
        for item in self.files[self.shown :]:
            action = menu.addAction(f"{item.kind}  {item.label}" if item.kind else item.label)
            action.setToolTip(str(item.path))
            action.triggered.connect(lambda _c=False, p=item.path: self.open_requested.emit(p))
        menu.popup(self.more.mapToGlobal(QPoint(0, self.more.height())))
