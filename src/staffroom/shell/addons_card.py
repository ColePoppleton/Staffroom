"""Settings > Add-ons (#5): one row per optional add-on, with what it is
for, which tools need it, its size, whether this copy has it, and Install or
Remove.

A change runs :func:`staffroom.core.addons.change` in a worker thread: the
row's button turns into a progress line, the installer's own messages go
behind *Details*, and nothing blocks the window. When it works the card asks
to restart Staffroom (a running app cannot load a new Qt module), and every
button waits for that restart. When it fails the card says why in one
sentence, never a traceback.

A copy that cannot change itself (a bundle, a pip install) shows the line to
paste instead of buttons.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from staffroom.core import addons, install
from staffroom.core.log import get_logger
from staffroom.core.plugin import ToolPlugin, plugin_requires
from staffroom.shell.widgets import Card, CommandBox, make_label
from staffroom.shell.worker import GuiWorker

log = get_logger(__name__)

#: ``change(wanted, *, log_line, progress) -> Outcome``; the real one is
#: :func:`staffroom.core.addons.change`. Tests pass one with a fake runner.
Changer = Callable[..., addons.Outcome]

INTRO = (
    "Optional parts that a few tools need, kept out of the normal install because they are "
    "large. Each is downloaded once, from the Python package index, when you press Install; "
    "nothing else about you or your files is sent."
)


class AddOnWorker(GuiWorker):
    """Runs one change of add-ons off the GUI thread."""

    line = Signal(str)  # a line of the installer's output
    step = Signal(str)  # a short progress line
    done = Signal(object)  # addons.Outcome

    def __init__(self, wanted: frozenset[str], change: Changer) -> None:
        super().__init__()
        self.wanted = wanted
        self.change = change

    def run(self) -> None:
        try:
            outcome = self.change(
                self.wanted,
                log_line=lambda m: self.line.emit(m),
                progress=lambda m: self.step.emit(m),
            )
        except Exception as exc:  # a bug in the plan: still one sentence on the card
            log.exception("add-on change failed")
            self.line.emit(f"{type(exc).__name__}: {exc}")
            outcome = addons.Outcome(False, addons.FAILED)
        self.done.emit(outcome)


class AddOnRow(QWidget):
    """One add-on: title and state, what it is for, its users and size, and
    its button."""

    def __init__(self, addon: addons.AddOn, users: list[str]) -> None:
        super().__init__()
        self.addon = addon
        self.users = users
        self.setObjectName("AddOnRow")
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 4, 0, 4)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(3)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(make_label(addon.title, "strong"))
        self.state = make_label("", "chip")
        self.state.setObjectName("AddOnState")
        head.addWidget(self.state)
        head.addStretch(1)
        grid.addLayout(head, 0, 0)
        grid.addWidget(make_label(addon.enables, "muted", wrap=True), 1, 0)
        used = f"Used by: {', '.join(users)}." if users else "No tool here needs it yet."
        self.details = make_label(f"{used} {addon.size_text()}", "faint", wrap=True)
        grid.addWidget(self.details, 2, 0)
        self.button = QPushButton("Install")
        self.button.setObjectName(f"AddOnButton-{addon.name}")
        grid.addWidget(self.button, 0, 1, 2, 1, Qt.AlignmentFlag.AlignRight)
        grid.setColumnStretch(0, 1)

    def show_state(self, installed: bool, note: str = "") -> None:
        self.state.setText(note or ("Installed" if installed else "Not installed"))
        self.button.setText("Remove" if installed else "Install")
        # Never red: on Settings nothing is the page's one primary action.
        self.button.setProperty("role", "ghost" if installed else "")
        self.button.style().unpolish(self.button)
        self.button.style().polish(self.button)


class AddOnsCard(Card):
    """The Add-ons card on the Settings page."""

    restart_requested = Signal()
    busy_changed = Signal(bool)
    finished = Signal(object)  # addons.Outcome, after a change

    def __init__(
        self,
        plugins: tuple[ToolPlugin, ...],
        installation: install.Installation | None = None,
        *,
        change: Changer | None = None,
        installed: frozenset[str] | None = None,
        confirm: Callable[[str, str], bool] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """``installation`` defaults to the running copy, ``change`` to the
        real installer, ``installed`` to what the running copy has, and
        ``confirm(title, text)`` to a question box (tests answer it)."""
        super().__init__("Add-ons", INTRO, parent)
        self.installation = installation or install.detect()
        self._change: Changer = change or (
            lambda wanted, **kw: addons.change(wanted, installation=self.installation, **kw)
        )
        self._confirm = confirm or self._ask
        self.installed = addons.installed() if installed is None else installed
        self.pending: frozenset[str] | None = None  # changed, waiting for a restart
        self.ask_after = True  # ask to restart when a change works (off while quitting)
        self.worker: AddOnWorker | None = None
        self.can_change = self.installation.kind is not install.InstallKind.OTHER

        self.how = make_label(self._how_text(), "faint", wrap=True)
        self.how.setObjectName("AddOnsHow")
        self.body.addWidget(self.how)
        self.rows: dict[str, AddOnRow] = {}
        for name, addon in addons.ADDONS.items():
            users = [p.panel_spec().title or p.name for p in plugins if name in plugin_requires(p)]
            row = AddOnRow(addon, users)
            row.button.clicked.connect(lambda _c=False, n=name: self.toggle(n))
            self.rows[name] = row
            self.body.addWidget(row)

        # How a change is going: a progress line, then the outcome. Hidden
        # (taking no room) until the first change.
        self.status_row = QWidget()
        status = QHBoxLayout(self.status_row)
        status.setContentsMargins(0, 0, 0, 0)
        status.setSpacing(10)
        self.progress = QProgressBar()
        self.progress.setObjectName("AddOnProgress")
        self.progress.setRange(0, 0)  # busy: uv gives no fraction
        self.progress.setFixedWidth(120)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.status = make_label("", "muted", wrap=True)
        self.status.setObjectName("AddOnStatus")
        self.details_button = QPushButton("Details ▸")
        self.details_button.setProperty("role", "link")
        self.details_button.setCheckable(True)
        self.details_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.details_button.toggled.connect(self._toggle_details)
        self.details_button.hide()
        self.restart_button = QPushButton("Restart Staffroom")
        self.restart_button.setProperty("role", "primary")
        self.restart_button.clicked.connect(self.restart_requested.emit)
        self.restart_button.hide()
        status.addWidget(self.progress, 0, Qt.AlignmentFlag.AlignVCenter)
        status.addWidget(self.status, 1)
        status.addWidget(self.details_button, 0, Qt.AlignmentFlag.AlignVCenter)
        status.addWidget(self.restart_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.status_row.hide()
        self.body.addWidget(self.status_row)
        self.log_view = QPlainTextEdit()
        self.log_view.setObjectName("AddOnLog")
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        self.log_view.setMaximumHeight(220)
        self.log_view.hide()
        self.body.addWidget(self.log_view)

        # A copy that cannot change itself: the line to paste.
        self.manual = QWidget()
        manual_layout = QVBoxLayout(self.manual)
        manual_layout.setContentsMargins(0, 0, 0, 0)
        manual_layout.setSpacing(6)
        self.manual_text = make_label("", wrap=True)
        self.manual_text.setObjectName("AddOnsManual")
        self.command_box = CommandBox()
        manual_layout.addWidget(self.manual_text)
        manual_layout.addWidget(self.command_box)
        self.manual.hide()
        self.body.addWidget(self.manual)
        self._show_rows()

    # -- what the card says ------------------------------------------------
    def _how_text(self) -> str:
        kind = self.installation.kind
        if kind is install.InstallKind.UV_TOOL:
            return (
                "This copy was installed with uv: Install re-installs it with uv, from the same "
                "place, with the add-on. Your settings and files are not touched."
            )
        if kind is install.InstallKind.CHECKOUT:
            return "This copy runs from its git checkout: Install adds the add-on with uv sync."
        return "This copy cannot add to itself: each add-on shows the line to install it with uv."

    def _show_rows(self) -> None:
        have = self.pending if self.pending is not None else self.installed
        busy = self.busy()
        for name, row in self.rows.items():
            note = ""
            if self.pending is not None and (name in self.pending) != (name in self.installed):
                note = "Restart to use" if name in self.pending else "Restart to finish"
            within = addons.included_in(name, have) if name in have else None
            if within is not None and not note:
                note = f"Comes with {within.title}"
            row.show_state(name in have, note)
            row.button.setEnabled(not busy and self.pending is None and within is None)
            if not self.can_change:
                row.button.setText("Show how")
                row.button.setEnabled(name not in have)
            tip = f"Included with {within.label}: remove that instead." if within else ""
            row.button.setToolTip(tip)

    def busy(self) -> bool:
        return self.worker is not None

    # -- changing ------------------------------------------------------------
    def toggle(self, name: str) -> None:
        """The row's button: install ``name``, or remove it."""
        if name in self.installed:
            self.remove(name)
        else:
            self.request_install(name)

    def request_install(self, name: str) -> None:
        """Install ``name`` after the teacher agrees (the row's button, and
        the Install button of a tool that needs it)."""
        addon = addons.get(name)
        if name in self.installed or self.busy() or self.pending is not None:
            return
        wanted = self.installed | {name}
        if not self.can_change:
            self._show_manual(wanted)
            return
        text = (
            f"{addon.enables} {addon.size_text()}\n\nStaffroom downloads it now and asks to "
            "restart when it is done. You can keep working meanwhile."
        )
        if self._confirm(f"Install {addon.label}?", text):
            self.start(wanted)

    def remove(self, name: str) -> None:
        addon = addons.get(name)
        if name not in self.installed or self.busy() or self.pending is not None:
            return
        users = self.rows[name].users
        needed = f" ({', '.join(users)})" if users else ""
        text = (
            f"Tools that need it{needed} are greyed out until you install it again, which "
            "downloads it again."
        )
        if self._confirm(f"Remove {addon.label}?", text):
            self.start(self.installed - {name})

    def start(self, wanted: frozenset[str]) -> None:
        """Change the add-ons to ``wanted`` in a worker."""
        if self.busy():
            return
        self.log_view.clear()
        self.manual.hide()
        self.restart_button.hide()
        self.status_row.show()
        self.progress.show()
        self.details_button.show()
        self._set_status("Starting…", "muted")
        worker = AddOnWorker(wanted, self._change)
        worker.line.connect(self.log_view.appendPlainText)
        worker.step.connect(lambda m: self._set_status(m, "muted"))
        worker.done.connect(lambda outcome, w=wanted: self._on_done(w, outcome))
        worker.finished.connect(self._on_worker_finished)
        self.worker = worker
        self._show_rows()
        self.busy_changed.emit(True)
        worker.start()

    def wait(self, timeout_ms: int) -> bool:
        worker = self.worker
        return worker is None or worker.wait(timeout_ms)

    def _on_worker_finished(self) -> None:
        worker, self.worker = self.worker, None
        if worker is not None:
            worker.deleteLater()
        self._show_rows()
        self.busy_changed.emit(False)

    def _on_done(self, wanted: frozenset[str], outcome: object) -> None:
        assert isinstance(outcome, addons.Outcome)
        self.progress.hide()
        if outcome.ok:
            self.pending = wanted
            self._set_status(outcome.message, "success")
        else:
            self._set_status(outcome.message, "danger")
            if outcome.restart:  # something changed even so
                self.pending = self.installed
        if outcome.command:
            self.manual_text.hide()
            self.command_box.set_command(outcome.command)
            self.manual.show()
        self.restart_button.setVisible(outcome.restart)
        self._show_rows()
        self.finished.emit(outcome)
        if outcome.ok and self.ask_after:
            self.ask_restart()

    def _show_manual(self, wanted: frozenset[str]) -> None:
        target = addons.plan(wanted, self.installation)
        self.manual_text.setText(target.why_manual)
        self.manual_text.show()
        self.command_box.set_command(target.manual)
        self.manual.show()

    def _set_status(self, text: str, role: str) -> None:
        self.status.setText(text)
        self.status.setProperty("role", role)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _toggle_details(self, shown: bool) -> None:
        self.log_view.setVisible(shown)
        self.details_button.setText("Details ▾" if shown else "Details ▸")

    def ask_restart(self) -> bool:
        """After a change: restart now? (Yes emits ``restart_requested``.)"""
        if self._confirm(
            "Restart Staffroom?",
            "The change takes effect when Staffroom starts again. Restart now?",
        ):
            self.restart_requested.emit()
            return True
        return False

    def _ask(self, title: str, text: str) -> bool:
        answer = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return answer == QMessageBox.StandardButton.Yes
