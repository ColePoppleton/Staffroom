"""The shared widget kit. Every piece of UI a tool can ask for lives here, keyed
by the dataclasses in :mod:`teaching_tools.core.panel`. New UI needs go here,
never into a tool package."""

from teaching_tools.shell.widgets.card import Card, Divider, make_label
from teaching_tools.shell.widgets.image_view import ImageViewWidget
from teaching_tools.shell.widgets.options_form import OptionsFormWidget
from teaching_tools.shell.widgets.path_picker import PathPickerWidget
from teaching_tools.shell.widgets.results import ResultsArea
from teaching_tools.shell.widgets.run_bar import RunBar
from teaching_tools.shell.widgets.table_view import (
    EditableTableWidget,
    TableModel,
    TablePreviewWidget,
    TableWidget,
)

__all__ = [
    "Card",
    "Divider",
    "EditableTableWidget",
    "ImageViewWidget",
    "OptionsFormWidget",
    "PathPickerWidget",
    "ResultsArea",
    "RunBar",
    "TableModel",
    "TablePreviewWidget",
    "TableWidget",
    "make_label",
]
