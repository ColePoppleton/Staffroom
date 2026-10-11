"""Shell settings, persisted straight to the TOML config."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from staffroom import __version__
from staffroom.core import install, paths
from staffroom.core.config import Config, NotSaved
from staffroom.core.launch import EDITOR_PRESETS, preset_for
from staffroom.core.library.exclude import IGNORE_FILE
from staffroom.core.library.service import library_db_path
from staffroom.core.library.tags import SIDECAR_DIR
from staffroom.core.panel import FolderPicker
from staffroom.shell.widgets import Card, PathPickerWidget, StringListEditor, make_label

LIBRARY_STORED_STATEMENT = (
    "What is stored: the index keeps file names and the text of .py, .txt, .md, .csv and "
    ".pdf files from this folder, nothing else, in a database at {db}. The folder is only "
    "ever read. Tags live in {sidecar}/tags.json inside it. A file whose text looks like it "
    "holds pupil details (candidate number, surname, UPN, date of birth near a value) is "
    "indexed by name only and counted in the status line. To remove the index, delete the "
    "database or change the folder: a full re-index drops the old entries."
)


class SettingsPage(QWidget):
    theme_changed = Signal(str)
    resources_root_changed = Signal(str)
    library_exclude_changed = Signal(object)  # list[str]
    # True / False after a check; None for an installed copy or a failed check,
    # so the sidebar never says "up to date" without having checked.
    update_available = Signal(object)

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(16)
        scroll.setWidget(content)
        root.addWidget(scroll)

        layout.addWidget(make_label("Settings", "title"))
        layout.addWidget(
            make_label("Shell-wide preferences. Saved as you change them.", "subtitle")
        )
        # Shown while config.toml cannot be written (#74): changes still apply.
        self.save_notice = make_label("", "danger", wrap=True)
        self.save_notice.setObjectName("SettingsSaveNotice")
        self.save_notice.setVisible(False)
        layout.addWidget(self.save_notice)

        appearance = Card("Appearance")
        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        self.theme = QComboBox()
        self.theme.addItems(["dark", "light"])
        self.theme.setCurrentText(config.general.theme)
        self.theme.currentTextChanged.connect(self._on_theme)
        form.addRow(self._label("Theme"), self.theme)
        appearance.body.addLayout(form)
        layout.addWidget(appearance)

        output = Card(
            "Output folder",
            "Where tools write their results. Leave empty to write next to the input file, "
            f"or to {paths.fallback_output_dir(config.general.sessions_root, '<tool>')} "
            "when a tool has no input file.",
        )
        self.output_dir = PathPickerWidget(FolderPicker(key="output_dir", label="Output folder"))
        self.output_dir.edit.setPlaceholderText("next to the input  (default)")
        if config.general.output_dir:
            self.output_dir.edit.setText(config.general.output_dir)
        self.output_dir.changed.connect(self._on_output_dir)
        output.add(self.output_dir)
        layout.addWidget(output)

        resources = Card(
            "Resources folder",
            "The folder the Resource Library indexes. Changing it triggers a full re-index.",
        )
        self.resources_root = PathPickerWidget(
            FolderPicker(key="resources_root", label="Resources folder")
        )
        self.resources_root.edit.setText(config.general.resources_root)
        self.resources_root.changed.connect(self._on_resources_root)
        resources.add(self.resources_root)
        self.library_statement = make_label(
            LIBRARY_STORED_STATEMENT.format(db=library_db_path(), sidecar=SIDECAR_DIR),
            "muted",
            wrap=True,
        )
        self.library_statement.setObjectName("LibraryStatement")
        resources.add(self.library_statement)
        reveal_row = QHBoxLayout()
        reveal_db = QPushButton("Reveal index database")
        reveal_db.setProperty("role", "ghost")
        reveal_db.clicked.connect(lambda: self._reveal(library_db_path().parent))
        reveal_row.addWidget(reveal_db)
        reveal_row.addStretch(1)
        resources.body.addLayout(reveal_row)
        resources.add(make_label("Exclude from the library", "section"))
        resources.add(
            make_label(
                "Folders and files that are neither indexed nor listed, for pupil work or "
                "anything else that should stay out. A name matches at any depth (Pupil work, "
                "*assessment*); a path matches from the root (Year 11/Mocks). Patterns in "
                f"{SIDECAR_DIR}/{IGNORE_FILE} inside the folder are honoured too. "
                "Changing the list re-indexes.",
                "muted",
                wrap=True,
            )
        )
        self.library_exclude = StringListEditor("Folder name, pattern or path…")
        self.library_exclude.set_values(config.general.library_exclude)
        self.library_exclude.changed.connect(self._on_library_exclude)
        resources.add(self.library_exclude)
        layout.addWidget(resources)

        classroom = Card(
            "Classroom",
            "Where lesson copies go and which editor opens them. The sessions folder is local "
            "by default; pick another folder only if you want copies synced somewhere.",
        )
        form2 = QFormLayout()
        form2.setHorizontalSpacing(16)
        form2.setVerticalSpacing(10)
        self.sessions_root = PathPickerWidget(
            FolderPicker(key="sessions_root", label="Sessions folder")
        )
        self.sessions_root.edit.setPlaceholderText(
            str(paths.sessions_root("")) + "  (default, local)"
        )
        if config.general.sessions_root:
            self.sessions_root.edit.setText(config.general.sessions_root)
        self.sessions_root.changed.connect(self._on_sessions_root)
        form2.addRow(self._label("Sessions folder"), self.sessions_root)
        self.editor_preset = QComboBox()
        self.editor_preset.addItems([*EDITOR_PRESETS, "Custom"])
        self.editor_preset.setCurrentText(preset_for(config.general.editor_command))
        self.editor_preset.currentTextChanged.connect(self._on_editor_preset)
        form2.addRow(self._label("Editor"), self.editor_preset)
        self.editor_command = QLineEdit(config.general.editor_command)
        self.editor_command.setPlaceholderText("open -a Thonny {file}")
        self.editor_command.setToolTip("{file} is replaced by the path of the lesson copy")
        self.editor_command.editingFinished.connect(self._on_editor_command)
        form2.addRow(self._label("Command"), self.editor_command)
        classroom.body.addLayout(form2)
        layout.addWidget(classroom)

        house = Card(
            "Worksheets",
            "Exam board for presets and tags, and the house style printed on every sheet.",
        )
        form3 = QFormLayout()
        form3.setHorizontalSpacing(16)
        form3.setVerticalSpacing(10)
        self.board = QComboBox()
        self.board.addItem("OCR J277", "ocr")
        self.board.addItem("AQA 8525", "aqa")
        self.board.setCurrentIndex(max(self.board.findData(config.general.board), 0))
        self.board.currentIndexChanged.connect(self._on_board)
        form3.addRow(self._label("Exam board"), self.board)
        self.house_header = QLineEdit(config.general.house_header)
        self.house_header.setPlaceholderText("e.g. Example High School · Computing")
        self.house_header.editingFinished.connect(self._on_house)
        form3.addRow(self._label("Header text"), self.house_header)
        self.house_footer = QLineEdit(config.general.house_footer)
        self.house_footer.setPlaceholderText("e.g. Computing Department")
        self.house_footer.editingFinished.connect(self._on_house)
        form3.addRow(self._label("Footer text"), self.house_footer)
        house.body.addLayout(form3)
        layout.addWidget(house)

        release = config.general.release_branch or "main"
        self.installation = install.detect()
        if self.installation.is_checkout:
            updates_help = (
                f"The app runs straight from the git checkout and follows the released "
                f"branch ({release}). An update is a fast-forward pull plus a dependency "
                f"sync; nothing is pulled while the checkout is on another branch, has local "
                f"edits or has diverged. Restart afterwards."
            )
        else:
            # Minimal until the Updates card for installed copies (#11) lands.
            updates_help = (
                "This copy is installed, not a git checkout: Staffroom never rewrites its "
                "own files and does not check for updates."
            )
        updates = Card("Updates", updates_help)
        self.version_label = make_label(self._version_text(__version__))
        self.version_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        updates.body.addWidget(self.version_label)
        update_row = QHBoxLayout()
        self.update_status = make_label("Checking…", "muted")
        self.check_button = QPushButton("Check for updates")
        self.check_button.setProperty("role", "ghost")
        self.check_button.clicked.connect(lambda: self.check_updates(fetch=True))
        self.update_button = QPushButton("Update now")
        self.update_button.setProperty("role", "primary")
        self.update_button.setEnabled(False)
        self.update_button.clicked.connect(self.apply_update)
        update_row.addWidget(self.update_status, 1)
        update_row.addWidget(self.check_button)
        update_row.addWidget(self.update_button)
        updates.body.addLayout(update_row)
        layout.addWidget(updates)
        if not self.installation.is_checkout:
            self._show_installed()

        logging_card = Card("Logging")
        log_form = QFormLayout()
        log_form.setHorizontalSpacing(16)
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level.setCurrentText(config.general.log_level.upper())
        self.log_level.currentTextChanged.connect(self._on_log_level)
        log_form.addRow(self._label("Level"), self.log_level)
        logging_card.body.addLayout(log_form)
        links = QHBoxLayout()
        open_config = QPushButton("Reveal config file")
        open_config.setProperty("role", "ghost")
        open_config.clicked.connect(lambda: self._reveal(paths.config_file().parent))
        open_logs = QPushButton("Reveal logs")
        open_logs.setProperty("role", "ghost")
        open_logs.clicked.connect(lambda: self._reveal(paths.log_dir()))
        links.addWidget(open_config)
        links.addWidget(open_logs)
        links.addStretch(1)
        logging_card.body.addLayout(links)
        path_label = make_label(str(paths.config_file()), "faint")
        logging_card.add(path_label)
        layout.addWidget(logging_card)
        layout.addStretch(1)

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("role", "muted")
        return label

    def _save(self) -> None:
        self.show_save_result(self.config.save())

    def show_save_result(self, problem: NotSaved | None) -> None:
        """Say under the title when the last save failed; a later save that
        works (the folder was unlocked) clears it. The change itself already
        applies in memory either way."""
        self.save_notice.setText(str(problem) if problem else "")
        self.save_notice.setVisible(problem is not None)

    def _on_theme(self, theme: str) -> None:
        if theme in ("dark", "light"):
            self.config.general.theme = theme  # type: ignore[assignment]
            self._save()
            self.theme_changed.emit(theme)

    def _on_resources_root(self, path: object) -> None:
        text = str(path) if path else ""
        if text and text != self.config.general.resources_root:
            self.config.general.resources_root = text
            self._save()
            self.resources_root_changed.emit(text)

    def _on_library_exclude(self, values: object) -> None:
        patterns = [str(v) for v in values] if isinstance(values, list) else []
        if patterns != self.config.general.library_exclude:
            self.config.general.library_exclude = patterns
            self._save()
            self.library_exclude_changed.emit(patterns)

    # -- updates ---------------------------------------------------------
    def check_updates(self, *, fetch: bool = True) -> None:
        from staffroom.shell.update_worker import UpdateWorker

        if not self.installation.is_checkout:
            self._show_installed()  # an installed copy never runs git (#9)
            return
        self.check_button.setEnabled(False)
        self.update_status.setText("Checking…")
        worker = UpdateWorker(fetch=fetch)
        worker.done.connect(self._on_update_status)
        worker.finished.connect(worker.deleteLater)
        self._update_worker = worker
        worker.start()

    def _on_update_status(self, status: object) -> None:
        from staffroom.core.update import UpdateStatus

        assert isinstance(status, UpdateStatus)
        if status.installed:
            self._show_installed(status.installed)
            return
        self.check_button.setEnabled(True)
        self.version_label.setText(self._version_text(status.running_version(__version__)))
        self.update_status.setText(status.describe())
        self.update_status.setProperty("role", "danger" if status.error else "muted")
        self.update_status.style().unpolish(self.update_status)
        self.update_status.style().polish(self.update_status)
        self.update_button.setEnabled(status.can_apply)
        if status.available and not status.can_apply:
            why = status.note or (
                "local edits would be overwritten"
                if status.dirty
                else "this copy has diverged from the release branch"
            )
            self.update_button.setToolTip(f"Not updating: {why}.")
        else:
            self.update_button.setToolTip("")
        self.update_available.emit(None if status.error else status.available)

    def _show_installed(self, line: str = "") -> None:
        """An installed copy: say how to update it, offer no check or pull,
        and leave the sidebar showing just the version."""
        self.update_status.setText(line or self.installation.update_hint())
        self.update_status.setWordWrap(True)
        self.update_status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.update_status.setProperty("role", "muted")
        self.update_status.style().unpolish(self.update_status)
        self.update_status.style().polish(self.update_status)
        self.check_button.hide()
        self.update_button.hide()
        self.update_available.emit(None)

    @staticmethod
    def _version_text(running: str) -> str:
        return f"Running Staffroom {running}"

    def apply_update(self) -> None:
        from staffroom.shell.update_worker import ApplyWorker

        self.update_button.setEnabled(False)
        self.update_status.setText("Updating…")
        worker = ApplyWorker()
        worker.done.connect(self._on_update_applied)
        worker.finished.connect(worker.deleteLater)
        self._apply_worker = worker
        worker.start()

    def _on_update_applied(self, message: str, ok: bool) -> None:
        self.update_status.setText(message)
        self.update_status.setProperty("role", "success" if ok else "danger")
        self.update_status.style().unpolish(self.update_status)
        self.update_status.style().polish(self.update_status)
        if ok:
            self.update_available.emit(False)

    def _on_board(self, index: int) -> None:
        self.config.general.board = str(self.board.itemData(index))
        self._save()

    def _on_house(self) -> None:
        header, footer = self.house_header.text().strip(), self.house_footer.text().strip()
        if (header, footer) != (self.config.general.house_header, self.config.general.house_footer):
            self.config.general.house_header = header
            self.config.general.house_footer = footer
            self._save()

    def _on_sessions_root(self, path: object) -> None:
        self.config.general.sessions_root = str(path) if path else ""
        self._save()

    def _on_editor_preset(self, name: str) -> None:
        if name in EDITOR_PRESETS:
            self.editor_command.setText(EDITOR_PRESETS[name])
            self._on_editor_command()

    def _on_editor_command(self) -> None:
        command = self.editor_command.text().strip()
        if command and command != self.config.general.editor_command:
            self.config.general.editor_command = command
            self._save()
            preset = preset_for(command)
            if self.editor_preset.currentText() != preset:
                self.editor_preset.blockSignals(True)
                self.editor_preset.setCurrentText(preset)
                self.editor_preset.blockSignals(False)

    def _on_output_dir(self, path: object) -> None:
        self.config.general.output_dir = str(path) if path else ""
        self._save()

    def _on_log_level(self, level: str) -> None:
        self.config.general.log_level = level
        self._save()

    @staticmethod
    def _reveal(folder: object) -> None:
        from pathlib import Path

        p = Path(str(folder))
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
