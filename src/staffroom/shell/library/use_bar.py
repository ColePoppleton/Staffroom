"""The use bar under a library file's title: what the teacher can do with it.

*Open for class* with the lesson label typed inline (Enter opens it), then one
button per tool that takes this kind of file. The buttons are not a list kept
here: the window hands over each visible tool's main file input
(:func:`staffroom.core.panel.main_file_input`, read from the tool's own panel
spec) and the bar shows the ones that accept the file, so a new tool appears
with no library change.

The bar only asks; the window does the work. *Open for class* is run by the
Classroom tool's own ``run`` (a copy in the sessions folder, the original never
touched), and a tool button opens that tool with the file already picked.

Some files are not for a lesson copy or a tool: Office files and the other
kinds the library never parses, files that are not downloaded, files indexed
by name only because they look like they hold pupil details. For those the
bar's main action is *Open externally*.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from staffroom.core.config import Theme
from staffroom.core.library.model import Resource
from staffroom.core.panel import FileInput, TextField, tools_accepting
from staffroom.shell.theme import glyph_icon, palette
from staffroom.shell.widgets.elided_label import ElidedLabel
from staffroom.shell.widgets.flow_layout import FlowLayout

# The kinds a lesson copy makes sense for: Classroom opens the copy in the
# teacher's editor (Thonny), which is a text editor.
LESSON_KINDS: frozenset[str] = frozenset({"python", "text", "markdown", "csv"})
LABEL_HINT = "Name the lesson first: one short line, never a class or a pupil."
ICON_SIZE = 14


@dataclass(frozen=True)
class UseTool:
    """A tool the bar can hand a file to."""

    name: str
    title: str
    glyph: str
    file_input: FileInput


class UseBar(QFrame):
    open_for_class = Signal(str)  # the lesson label
    tool_requested = Signal(str)  # a tool name
    open_requested = Signal()  # open the original in its own app
    classroom_requested = Signal()  # the link to Classroom after a copy

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("UseBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.theme: Theme = "dark"
        self.tools: list[UseTool] = []
        self.buttons: dict[str, QPushButton] = {}
        self.has_classroom = False
        self.resource: Resource | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        # One line of actions, wrapping onto a second at narrow widths.
        self.action_row = QWidget()
        self.row = FlowLayout(self.action_row, spacing=6)
        outer.addWidget(self.action_row)

        # -- Open for class: the button and its lesson label, one control
        self.class_group = QFrame()
        self.class_group.setObjectName("OpenForClass")
        self.class_group.setProperty("role", "primary")  # the page's one red action
        self.class_group.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        group = QHBoxLayout(self.class_group)
        group.setContentsMargins(0, 0, 0, 0)
        group.setSpacing(0)
        self.class_button = QPushButton("Open for class")
        self.class_button.setObjectName("OpenForClassButton")
        self.class_button.setProperty("role", "primary")
        self.class_button.setToolTip(
            "Copy this file into today's session folder and open the copy in your editor "
            "(⌘O). The original is never touched."
        )
        self.class_button.clicked.connect(self.submit)
        self.label = QLineEdit()
        self.label.setObjectName("LessonLabel")
        self.label.setPlaceholderText("Lesson label")
        self.label.setMaxLength(60)
        self.label.setFixedWidth(128)
        self.label.returnPressed.connect(self.submit)
        self.label.textEdited.connect(lambda _t: self.clear_status())
        group.addWidget(self.class_button)
        group.addWidget(self.label)
        self.row.addWidget(self.class_group)

        self.open_button = QPushButton("Open externally")
        self.open_button.setProperty("role", "primary")
        self.open_button.setToolTip("Open the original in its own app. Staffroom never parses it.")
        self.open_button.clicked.connect(self.open_requested.emit)
        self.row.addWidget(self.open_button)

        # -- what the last Open for class did (or why it did not)
        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        self.status = ElidedLabel(max_lines=2, whole_words=True)
        self.status.setObjectName("UseStatus")
        self.classroom_link = QPushButton("Classroom ›")
        self.classroom_link.setProperty("role", "link")
        self.classroom_link.setToolTip("Today's sessions: diff, re-open or promote the copy")
        self.classroom_link.clicked.connect(self.classroom_requested.emit)
        status_row.addWidget(self.status, 1)
        status_row.addWidget(self.classroom_link, 0, Qt.AlignmentFlag.AlignTop)
        self.status_box = QWidget()
        self.status_box.setLayout(status_row)
        status_row.setContentsMargins(4, 0, 0, 0)
        self.status_box.hide()
        outer.addWidget(self.status_box)

        # The flow's minimum is its widest action: the bar never widens the window.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    # -- set-up ------------------------------------------------------------
    def set_tools(
        self, tools: Sequence[UseTool], *, classroom: bool, label: TextField | None = None
    ) -> None:
        """The tools that may appear (visible ones, in sidebar order) and
        whether Classroom is installed. ``label`` is Classroom's own lesson
        label field, so the inline field keeps its placeholder and limit."""
        self.tools = list(tools)
        self.has_classroom = classroom
        if label is not None:
            self.label.setPlaceholderText(label.label)
            self.label.setMaxLength(label.max_length)
            example = f" ({label.placeholder})" if label.placeholder else ""
            self.label.setToolTip(f"{label.help}{example} Enter opens it for class.")
        for button in self.buttons.values():
            self.row.removeWidget(button)
            button.deleteLater()
        self.buttons = {}
        for tool in self.tools:
            button = QPushButton(tool.title)
            button.setObjectName("UseTool")
            button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
            button.setToolTip(f"Open {tool.title} with this file already picked")
            button.clicked.connect(lambda _c=False, n=tool.name: self.tool_requested.emit(n))
            self.row.addWidget(button)
            self.buttons[tool.name] = button
        self._paint_icons()
        if self.resource is not None:
            self.show_for(self.resource)

    def set_theme(self, theme: Theme) -> None:
        self.theme = theme
        self._paint_icons()

    def _paint_icons(self) -> None:
        color = palette(self.theme).text_muted
        for tool in self.tools:
            self.buttons[tool.name].setIcon(glyph_icon(tool.glyph, color, ICON_SIZE))

    # -- per file ----------------------------------------------------------
    def lesson_copy_offered(self, resource: Resource) -> bool:
        return (
            self.has_classroom
            and resource.kind in LESSON_KINDS
            and not resource.cloud_only
            and not resource.text_withheld
        )

    def tools_offered(self, resource: Resource) -> list[str]:
        """The tools shown for ``resource``, in order. None for a file that is
        not on this Mac or that looks like it holds pupil details."""
        if resource.cloud_only or resource.text_withheld:
            return []
        inputs = {tool.name: tool.file_input for tool in self.tools}
        return tools_accepting(inputs, resource.name)

    def show_for(self, resource: Resource) -> None:
        if self.resource is None or resource.rel_path != self.resource.rel_path:
            self.clear_status()
        self.resource = resource
        lesson = self.lesson_copy_offered(resource)
        self.class_group.setVisible(lesson)
        self.open_button.setVisible(not lesson)
        offered = set(self.tools_offered(resource))
        for name, button in self.buttons.items():
            button.setVisible(name in offered)

    def visible_tools(self) -> list[str]:
        """The tool buttons showing, in order (for tests and the docs)."""
        return [t.name for t in self.tools if self.buttons[t.name].isVisibleTo(self)]

    # -- open for class ----------------------------------------------------
    def submit(self) -> None:
        """Open for class with the typed label, or ask for one."""
        if not self.class_group.isVisibleTo(self):
            return
        label = self.label.text().strip()
        if not label:
            self.label.setFocus()
            self.show_status(LABEL_HINT, ok=None)
            return
        self.show_status("Copying…", ok=None)
        self.open_for_class.emit(label)

    def focus_label(self) -> None:
        self.label.setFocus()
        self.label.selectAll()

    def show_status(self, text: str, *, ok: bool | None, link: bool = False) -> None:
        """``ok`` None: a neutral hint; True: done; False: it failed."""
        self.status.setText(text)
        role = "muted" if ok is None else ("success" if ok else "danger")
        self.status.setProperty("role", role)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.classroom_link.setVisible(link)
        self.status_box.show()

    def clear_status(self) -> None:
        self.status.setText("")
        self.status_box.hide()
