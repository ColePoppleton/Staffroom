"""What the kit shows when an add-on is missing (#5).

* :class:`AddOnNeeded`: the card a tool whose ``requires`` add-on is missing
  shows in place of its panel: what the add-on is for, its size, and one
  button that installs it (the window takes it from there, in Settings >
  Add-ons, so there is one installer).
* :class:`AddOnBanner`: one line for a kit widget that has a fallback (a
  basic HTML view in place of the Web add-on's browser engine): it says what
  is missing and offers the install, while the widget carries on.
* :func:`import_addon`: how a kit widget loads a Qt module that an add-on
  brings: only when the add-on is installed, never at module level, so the
  app still starts without it.

Every ``install_requested`` carries the add-on's name.
"""

from __future__ import annotations

import importlib
from types import ModuleType

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from staffroom.core import addons
from staffroom.core.log import get_logger
from staffroom.shell.widgets.card import make_label

log = get_logger(__name__)

SETTINGS_PLACE = "Settings › Add-ons"


def import_addon(name: str, module: str) -> ModuleType | None:
    """``PySide6.<module>`` when the add-on ``name`` is installed, else None
    (and None if it fails to load, which is logged). Call it where the
    widget is built, never at import time."""
    if not addons.is_installed(name):
        return None
    try:
        return importlib.import_module(f"PySide6.{module}")
    except ImportError:
        log.exception("the %s add-on is installed but %s does not load", name, module)
        return None


class AddOnNeeded(QFrame):
    """A tool's page while an add-on it requires is missing."""

    install_requested = Signal(str)

    def __init__(
        self,
        tool_title: str,
        missing: tuple[addons.AddOn, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("AddOnNeeded")
        self.missing = missing
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 26)
        layout.setSpacing(10)
        self.heading = make_label(addons.needs_text(missing), "section")
        self.heading.setObjectName("AddOnNeededTitle")
        layout.addWidget(self.heading)
        known = [a for a in missing if a.name in addons.ADDONS]
        what = " ".join(a.enables for a in known)
        intro = make_label(
            f"{tool_title} cannot open without it. {what}".strip(), "muted", wrap=True
        )
        layout.addWidget(intro)
        self.buttons: dict[str, QPushButton] = {}
        for addon in known:
            layout.addWidget(make_label(f"{addon.title}: {addon.size_text()}", "faint", wrap=True))
        row = QHBoxLayout()
        row.setSpacing(10)
        for addon in known:
            button = QPushButton(f"Install {addon.label}")
            button.setProperty("role", "primary")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _c=False, n=addon.name: self.install_requested.emit(n))
            self.buttons[addon.name] = button
            row.addWidget(button)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addWidget(
            make_label(
                f"Installing happens in {SETTINGS_PLACE}, which shows its progress. "
                "Restart Staffroom afterwards.",
                "faint",
                wrap=True,
            )
        )
        if not known:
            layout.addWidget(
                make_label("This version of Staffroom does not know that add-on.", "danger")
            )


class AddOnBanner(QFrame):
    """One line over a kit widget that works without an add-on, less well:
    what the add-on would add, and a link that installs it."""

    install_requested = Signal(str)

    def __init__(self, name: str, text: str, parent: QWidget | None = None) -> None:
        """``text`` says what the widget does instead ("Pages show in a basic
        viewer."); the banner adds the offer."""
        super().__init__(parent)
        self.setObjectName("AddOnBanner")
        self.addon = addons.get(name)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 6, 8, 6)
        row.setSpacing(10)
        self.text = make_label(f"{text} {self.addon.sentence_label} does more.", wrap=True)
        self.text.setProperty("role", "muted")
        self.link = QPushButton(f"Install {self.addon.label}…")
        self.link.setProperty("role", "link")
        self.link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link.clicked.connect(lambda: self.install_requested.emit(self.addon.name))
        row.addWidget(self.text, 1)
        row.addWidget(self.link, 0, Qt.AlignmentFlag.AlignVCenter)
