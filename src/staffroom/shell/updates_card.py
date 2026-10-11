"""Settings > Updates for an installed copy (#11): the version running, the
newest release on GitHub with its notes, and the one command that updates.

A git checkout keeps its own card in :mod:`staffroom.shell.settings_page`.
This card never runs git and never installs anything (the 2026-10-11 audit
refused in-app self-update this phase): it asks GitHub's Releases API, via
:func:`staffroom.core.update.check_latest_release` in a worker thread, when
the teacher presses *Check again* and at start at most once a day while the
tick box is on, and keeps the last answer for the next start.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from staffroom import __version__
from staffroom.core import install, update
from staffroom.core.config import Config
from staffroom.core.update import ReleaseCheck
from staffroom.shell.widgets import Card, CommandBox, make_label

ASKED = "github.com/ColePoppleton/Staffroom"
STEPS = "quit Staffroom, paste this into Terminal, then open Staffroom again."


class InstalledUpdatesCard(Card):
    """The Updates card of an installed copy."""

    # (newest version when it is ahead of this copy else "", up to date):
    # up to date is None until a check has answered and after a failed one.
    state_changed = Signal(str, object)

    def __init__(
        self,
        config: Config,
        installation: install.Installation,
        save: Callable[[], object] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """``save`` writes the config (Settings passes its own, which shows a
        save failure under the page title); default ``config.save``."""
        if installation.kind is install.InstallKind.UV_TOOL:
            intro = (
                "This copy was installed with uv. Staffroom never rewrites its own files: "
                "an update is one line in Terminal."
            )
        else:
            intro = (
                "This copy was not installed with uv. Staffroom never rewrites its own files: "
                "update it the way it was installed."
            )
        super().__init__("Updates", intro, parent)
        self.config = config
        self.installation = installation
        self._save: Callable[[], object] = save or config.save
        self.last: ReleaseCheck | None = update.load_release_check()
        self._worker: QThread | None = None
        self._notes_for = ""

        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)
        grid.setColumnMinimumWidth(0, 140)
        grid.addWidget(make_label("This copy", "muted"), 0, 0)
        self.this_copy = make_label(__version__, "strong")
        self.this_copy.setObjectName("ThisCopy")
        self.this_copy.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        grid.addWidget(self.this_copy, 0, 1)
        grid.addWidget(make_label("Newest release", "muted"), 1, 0)
        newest = self._newest_row = QHBoxLayout()
        newest.setSpacing(10)
        self.newest = make_label("", "strong", wrap=True)
        self.newest.setObjectName("NewestRelease")
        self.new_chip = make_label("new", "chip-new")
        self.new_chip.setObjectName("NewChip")
        self.whats_changed = QPushButton("What changed ▸")
        self.whats_changed.setProperty("role", "link")
        self.whats_changed.setCheckable(True)
        self.whats_changed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.whats_changed.toggled.connect(self._toggle_notes)
        center = Qt.AlignmentFlag.AlignVCenter
        newest.addWidget(self.newest, 0, center)
        newest.addWidget(self.new_chip, 0, center)
        newest.addWidget(self.whats_changed, 0, center)
        newest.addStretch(1)
        grid.addLayout(newest, 1, 1)
        self.check_button = QPushButton("Check again")
        self.check_button.setToolTip(f"Ask {ASKED} for its newest release")
        self.check_button.clicked.connect(self.check_now)
        grid.addWidget(self.check_button, 1, 2, Qt.AlignmentFlag.AlignRight)
        grid.setColumnStretch(1, 1)
        self.body.addLayout(grid)

        # The release notes, folded under *What changed*; images are dropped
        # and links open in the browser, so the card itself fetches nothing.
        self.notes_panel = QWidget()
        notes_layout = QVBoxLayout(self.notes_panel)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setSpacing(4)
        self.notes = QTextBrowser()
        self.notes.setObjectName("ReleaseNotes")
        self.notes.setOpenLinks(False)
        self.notes.anchorClicked.connect(QDesktopServices.openUrl)
        self.notes.setMinimumHeight(120)
        self.notes.setMaximumHeight(240)
        self.open_release = QPushButton("Open this release on GitHub ↗")
        self.open_release.setProperty("role", "link")
        self.open_release.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_release.clicked.connect(self._open_release_page)
        notes_layout.addWidget(self.notes)
        notes_layout.addWidget(self.open_release, 0, Qt.AlignmentFlag.AlignLeft)
        self.notes_panel.hide()
        self.body.addWidget(self.notes_panel)

        command = installation.update_command
        self.steps = make_label("", wrap=True)
        self.steps.setObjectName("UpdateSteps")
        self.command_box = CommandBox(command)
        self.pinned_note = make_label(
            "This copy was installed from a fixed release, so this once the command is the "
            f"install line; after that, {install.UV_UPGRADE_COMMAND} is enough.",
            "muted",
            wrap=True,
        )
        self.pinned_note.setVisible(bool(command) and not installation.tracks_main)
        self.body.addWidget(self.steps)
        self.body.addWidget(self.command_box)
        self.body.addWidget(self.pinned_note)
        if not command:
            self.command_box.hide()

        self.asked = make_label("", "faint", wrap=True)
        self.asked.setObjectName("ReleaseCheckNote")
        self.body.addWidget(self.asked)
        self.on_start = QCheckBox("Look for a new release when Staffroom opens")
        self.on_start.setChecked(config.general.check_for_releases)
        self.on_start.toggled.connect(self._on_start_toggled)
        self.body.addWidget(self.on_start)
        self.show_check(self.last)

    # -- checking ----------------------------------------------------------
    def check_on_start(self) -> None:
        """The start check: only while the tick box is on, and at most once
        a day (a failed ask counts too). The window never calls this in
        screenshot mode."""
        if self.config.general.check_for_releases and update.release_check_due(self.last):
            self.check_now()

    def check_now(self) -> None:
        """Ask GitHub now, in a worker thread (*Check again*)."""
        from staffroom.shell.update_worker import ReleaseWorker

        if self._worker is not None:
            return
        self.check_button.setEnabled(False)
        self.check_button.setText("Checking…")
        worker = ReleaseWorker()
        worker.done.connect(self._on_checked)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def wait(self, timeout_ms: int) -> bool:
        """Wait for a check still running, so no thread outlives the window."""
        worker = self._worker
        return worker is None or worker.wait(timeout_ms)

    def _on_worker_finished(self) -> None:
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.deleteLater()

    def _on_checked(self, check: object) -> None:
        assert isinstance(check, ReleaseCheck)
        self.last = check
        if not self.config.read_only:
            update.save_release_check(check)
        self.show_check(check)

    # -- showing -------------------------------------------------------------
    def show_check(self, check: ReleaseCheck | None) -> None:
        """Lay the card out for ``check`` (None: never asked) and tell the
        sidebar what it may say."""
        self.check_button.setEnabled(True)
        self.check_button.setText("Check again" if check is not None else "Check now")
        newer = check.newer_than(__version__) if check is not None else None
        release = check.release if check is not None and check.ok else None
        if release is not None:
            date = update.release_date_text(release.published)
            self.newest.setText(f"{release.version} · {date}" if date else release.version)
            self._set_role(self.newest, "strong")
        elif check is not None:
            self.newest.setText(check.error)
            self._set_role(self.newest, "muted")
        else:
            self.newest.setText("Not checked yet")
            self._set_role(self.newest, "muted")
        # A failure sentence takes the row; a version leaves room after it.
        self._newest_row.setStretchFactor(self.newest, 0 if release is not None else 10)
        self.new_chip.setVisible(bool(newer))
        self.whats_changed.setVisible(release is not None)
        if release is None:
            self.whats_changed.setChecked(False)
        elif self._notes_for != release.version:
            self.notes.setMarkdown(update.notes_for_display(release.notes))
            self._notes_for = release.version

        if not self.command_box.command():
            self.steps.setText(self.installation.update_hint())
        elif newer is False:
            self.steps.setText(f"You have the newest release. When a newer one is out: {STEPS}")
        else:
            self.steps.setText(f"To update: {STEPS}")

        privacy = "Nothing about you or your files is sent."
        if check is None:
            self.asked.setText(
                f"The check asks {ASKED} for its newest release, and nothing else. {privacy}"
            )
        else:
            verb = "Checked" if check.ok else "Tried"
            when = update.age_text(check.checked_at)
            self.asked.setText(f"{verb} {when} by asking {ASKED} for its newest release. {privacy}")
        self.state_changed.emit(
            release.version if newer and release is not None else "",
            None if newer is None else not newer,
        )

    def announce(self) -> None:
        """Say the current state again (the window calls this once its
        sidebar is listening)."""
        self.show_check(self.last)

    def _toggle_notes(self, shown: bool) -> None:
        self.notes_panel.setVisible(shown)
        self.whats_changed.setText("What changed ▾" if shown else "What changed ▸")

    def _open_release_page(self) -> None:
        release = self.last.release if self.last is not None else None
        QDesktopServices.openUrl(QUrl(release.url if release else update.RELEASES_PAGE))

    def _on_start_toggled(self, on: bool) -> None:
        self.config.general.check_for_releases = on
        self._save()

    @staticmethod
    def _set_role(widget: QWidget, role: str) -> None:
        widget.setProperty("role", role)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
