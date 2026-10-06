"""Shell settings, persisted straight to the TOML config."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from teaching_tools.core import paths
from teaching_tools.core.config import Config
from teaching_tools.core.panel import FolderPicker
from teaching_tools.shell.widgets import Card, PathPickerWidget, make_label


class SettingsPage(QWidget):
    theme_changed = Signal(str)
    resources_root_changed = Signal(str)

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
            "Where tools write their results. Leave empty to write next to the input file.",
        )
        self.output_dir = PathPickerWidget(FolderPicker(key="output_dir", label="Output folder"))
        if config.general.output_dir:
            self.output_dir.edit.setText(config.general.output_dir)
        self.output_dir.changed.connect(self._on_output_dir)
        output.add(self.output_dir)
        layout.addWidget(output)

        resources = Card(
            "Resources folder",
            "The folder the Resource Library indexes. It is only ever read; tags live in a "
            "sidecar file inside it. Changing it triggers a full re-index.",
        )
        self.resources_root = PathPickerWidget(
            FolderPicker(key="resources_root", label="Resources folder")
        )
        self.resources_root.edit.setText(config.general.resources_root)
        self.resources_root.changed.connect(self._on_resources_root)
        resources.add(self.resources_root)
        layout.addWidget(resources)

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

    def _on_theme(self, theme: str) -> None:
        if theme in ("dark", "light"):
            self.config.general.theme = theme  # type: ignore[assignment]
            self.config.save()
            self.theme_changed.emit(theme)

    def _on_resources_root(self, path: object) -> None:
        text = str(path) if path else ""
        if text and text != self.config.general.resources_root:
            self.config.general.resources_root = text
            self.config.save()
            self.resources_root_changed.emit(text)

    def _on_output_dir(self, path: object) -> None:
        self.config.general.output_dir = str(path) if path else ""
        self.config.save()

    def _on_log_level(self, level: str) -> None:
        self.config.general.log_level = level
        self.config.save()

    @staticmethod
    def _reveal(folder: object) -> None:
        from pathlib import Path

        p = Path(str(folder))
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
