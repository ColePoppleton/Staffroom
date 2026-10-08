"""The first-run card: one question, "where are your resources?".

Shown by the launcher instead of a tool when no resources folder is set. It
never suggests a folder: the dialog opens at the home folder and the teacher
picks, because which folder is reachable from school (and whether it is
cloud-synced) is their call, not the app's.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from staffroom.core.panel import FolderPicker
from staffroom.shell.widgets.card import Card, make_label
from staffroom.shell.widgets.path_picker import PathPickerWidget

CARD_WIDTH = 560

PRIVACY_GUIDE_URL = (
    "https://colepoppleton.github.io/Staffroom/guide/privacy/#what-the-resource-library-stores"
)

INTRO = (
    "Staffroom lists and searches the folder where you keep your teaching resources, so a "
    "tool can open a file from it in a click. Pick the folder you already use. The app only "
    "reads it; nothing in it is changed."
)
STORED = (
    "What is stored: file names and the text of .py, .txt, .md, .csv and .pdf files, in a "
    "database on this Mac. Nothing is sent anywhere. The details are under Settings › "
    "Resources folder and in the privacy guide, “What the Resource Library stores”."
)


class FirstRunCard(QWidget):
    """``folder_chosen(str)`` fires with an existing folder; ``dismissed`` when
    the teacher chooses "Not now" (or "Continue" while the first index runs).
    The host saves the folder, starts the index and feeds
    :meth:`show_progress` / :meth:`finish_indexing`."""

    folder_chosen = Signal(str)
    dismissed = Signal()

    def __init__(self, sessions_default: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FirstRunPage")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 24)
        outer.addStretch(1)

        self.card = Card()
        self.card.setMaximumWidth(CARD_WIDTH)
        body = self.card.body
        body.setSpacing(12)

        self.title = make_label("Choose your resources folder", "title")
        body.addWidget(self.title)
        self.intro = make_label(INTRO, "muted", wrap=True)
        body.addWidget(self.intro)

        self.picker = PathPickerWidget(FolderPicker(key="resources_root", label="Resources folder"))
        self.picker.button.setText("Choose…")
        self.picker.button.setProperty("role", "primary")
        self.picker.changed.connect(self._on_picked)
        body.addWidget(self.picker)

        self.hint = make_label("", "danger", wrap=True)
        self.hint.hide()
        body.addWidget(self.hint)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        self.progress.hide()
        body.addWidget(self.progress)
        self.status = make_label("", "faint", wrap=True)
        self.status.hide()
        body.addWidget(self.status)

        self.sessions_note = make_label(
            f"Lesson copies made by Classroom will go to {sessions_default} (a plain local "
            "folder). Both folders can be changed later in Settings.",
            "muted",
            wrap=True,
        )
        body.addWidget(self.sessions_note)
        self.stored_note = make_label(STORED, "faint", wrap=True)
        body.addWidget(self.stored_note)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.guide_button = QPushButton("Privacy guide")
        self.guide_button.setProperty("role", "ghost")
        self.guide_button.setToolTip(PRIVACY_GUIDE_URL)
        self.guide_button.clicked.connect(self.open_guide)
        self.later_button = QPushButton("Not now")
        self.later_button.setProperty("role", "ghost")
        self.later_button.setToolTip("Carry on without a folder; choose one in Settings later")
        self.later_button.clicked.connect(self.dismissed.emit)
        buttons.addWidget(self.guide_button)
        buttons.addStretch(1)
        buttons.addWidget(self.later_button)
        body.addLayout(buttons)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(2)

    # -- for the host and the tests ----------------------------------------
    @property
    def choose_button(self) -> QPushButton:
        return self.picker.button

    def labels(self) -> list[QLabel]:
        """Every sentence on the card, for tests that check what it says."""
        return [
            self.title,
            self.intro,
            self.hint,
            self.status,
            self.sessions_note,
            self.stored_note,
        ]

    def show_progress(self, done: int, total: int, rel: str) -> None:
        if total:
            self.progress.setValue(int(1000 * done / total))
        if rel:
            self.status.setText(f"Indexing {done}/{total}: {rel}")

    def finish_indexing(self, summary: str) -> None:
        self.progress.setValue(self.progress.maximum())
        self.status.setText(summary)

    @staticmethod
    def open_guide() -> None:
        QDesktopServices.openUrl(QUrl(PRIVACY_GUIDE_URL))

    # -- internals ---------------------------------------------------------
    def _on_picked(self, path: object) -> None:
        if not path:
            self.hint.hide()
            return
        folder = Path(str(path))
        if not folder.is_dir():
            self.hint.setText(f"That folder does not exist: {folder}")
            self.hint.show()
            return
        self.hint.hide()
        self.picker.setEnabled(False)  # the choice is made; the index starts now
        self.progress.setValue(0)
        self.progress.show()
        self.status.setText("Indexing…")
        self.status.show()
        self.later_button.setText("Continue")
        self.later_button.setToolTip("Go to the tools; the index carries on in the background")
        self.folder_chosen.emit(str(folder))
