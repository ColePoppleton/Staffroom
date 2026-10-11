"""Neutral paths in docs screenshots (#14).

A screenshot is rendered from a throwaway config home, a temporary output
folder and the fixture resources inside a checkout, so the real paths are
temp and worktree paths: noise to a reader, and a maintainer's folders on a
public page. Just before the window is grabbed, every path it shows is
rewritten to the folder a teacher would see on their own Mac
(``~/Documents/Teaching resources``, ``~/TeachingSessions/outputs/marks``…).
Only the pixels change: the config is not touched, and any run has finished.

Whatever still looks like a machine-specific path after that is a leak, and
the screenshot is refused rather than saved (:func:`leaks`).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import QAbstractButton, QLabel, QLineEdit, QWidget

from staffroom.core import paths
from staffroom.core.config import Config
from staffroom.shell.widgets.run_bar import RunBar, abbreviate_path

NEUTRAL_RESOURCES = "~/Documents/Teaching resources"
NEUTRAL_SESSIONS = "~/TeachingSessions"
NEUTRAL_HOME = "~/.config/staffroom"
NEUTRAL_CHECKOUT = "~/Staffroom"

# Fragments that only appear in a path on the machine that made the image.
LEAKS = ("/Users/", "/home/", "/var/folders/", "/private/", "worktrees", "/tmp/")

Aliases = list[tuple[str, str]]


def aliases(config: Config, default_output: Path | None = None) -> Aliases:
    """Real path prefixes and what to show instead, longest first.

    Screenshot mode writes into a throwaway folder; it is shown as
    ``default_output``, where the run would have written with no output folder
    set (next to the input, or ``<sessions>/outputs/<tool>``), itself made
    neutral by the other aliases."""
    outputs = f"{NEUTRAL_SESSIONS}/{paths.OUTPUTS_SUBDIR}"
    if default_output is not None:
        outputs = neutral(str(default_output), aliases(config))
    pairs: list[tuple[str, str]] = []
    for real, shown in (
        (config.general.output_dir, outputs),
        (config.general.resources_root, NEUTRAL_RESOURCES),
        (str(paths.sessions_root(config.general.sessions_root)), NEUTRAL_SESSIONS),
        (str(paths.home_dir()), NEUTRAL_HOME),
        (str(paths.project_root()), NEUTRAL_CHECKOUT),
        (str(Path.home()), "~"),
    ):
        if not real:
            continue
        path = Path(real).expanduser()
        for variant in {str(path), str(path.resolve())}:  # /var is /private/var on macOS
            if variant not in ("/", "."):
                pairs.append((variant, shown))
    return sorted(set(pairs), key=lambda pair: len(pair[0]), reverse=True)


def neutral(text: str, table: Aliases) -> str:
    for real, shown in table:
        text = text.replace(real, shown)
    return text


def neutralise(window: QWidget, table: Aliases, blank: str = "") -> None:
    """Rewrite every path the window shows. A field holding exactly ``blank``
    (the throwaway output folder, which is not a setting) is shown empty, as
    a fresh install has it. The run bar's folder is rebuilt from its path,
    since the label holds an already shortened form."""
    for widget in window.findChildren(QLabel) + window.findChildren(QAbstractButton):
        _replace(widget, widget.text(), widget.setText, table)
    for edit in window.findChildren(QLineEdit):
        if blank and edit.text() == blank:
            with QSignalBlocker(edit):
                edit.clear()
        _replace(edit, edit.text(), edit.setText, table)
        _replace(edit, edit.placeholderText(), edit.setPlaceholderText, table)
    for bar in window.findChildren(RunBar):
        folder = bar._folder
        if folder is not None:
            shown = abbreviate_path(Path(neutral(str(folder), table)))
            with QSignalBlocker(bar.folder):
                bar.folder.setText(f"{bar._verb} {shown}")


def leaks(window: QWidget) -> list[str]:
    """The visible texts that still name a folder on this machine."""
    found = []
    widgets = window.findChildren(QLabel) + window.findChildren(QAbstractButton)
    texts: list[tuple[QWidget, str]] = [(w, w.text()) for w in widgets]
    for edit in window.findChildren(QLineEdit):
        texts += [(edit, edit.text()), (edit, edit.placeholderText())]
    for widget, text in texts:
        if widget.isVisibleTo(window) and any(fragment in text for fragment in LEAKS):
            found.append(text)
    return found


def _replace(widget: QWidget, text: str, setter: Callable[[str], object], table: Aliases) -> None:
    new = neutral(text, table)
    if new != text:
        with QSignalBlocker(widget):  # Settings saves on edit; nothing must change
            setter(new)
