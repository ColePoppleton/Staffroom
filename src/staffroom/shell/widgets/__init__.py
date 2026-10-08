"""The shared widget kit. Every piece of UI a tool can ask for lives here, keyed
by the dataclasses in :mod:`staffroom.core.panel`. New UI needs go here,
never into a tool package."""

from staffroom.shell.widgets.action_table import ActionTableWidget
from staffroom.shell.widgets.card import Card, Divider, make_label
from staffroom.shell.widgets.first_run import FirstRunCard
from staffroom.shell.widgets.image_view import ImageViewWidget
from staffroom.shell.widgets.options_form import OptionsFormWidget
from staffroom.shell.widgets.path_picker import PathPickerWidget
from staffroom.shell.widgets.resource_picker import ResourcePickerWidget
from staffroom.shell.widgets.results import ResultsArea
from staffroom.shell.widgets.run_bar import RunBar
from staffroom.shell.widgets.string_list import StringListEditor
from staffroom.shell.widgets.table_view import (
    EditableTableWidget,
    TableModel,
    TablePreviewWidget,
    TableWidget,
)
from staffroom.shell.widgets.text_area import TextAreaWidget
from staffroom.shell.widgets.text_field import TextFieldWidget
from staffroom.shell.widgets.text_view import TextViewWidget

__all__ = [
    "ActionTableWidget",
    "Card",
    "Divider",
    "EditableTableWidget",
    "FirstRunCard",
    "ImageViewWidget",
    "OptionsFormWidget",
    "PathPickerWidget",
    "ResourcePickerWidget",
    "ResultsArea",
    "RunBar",
    "StringListEditor",
    "TableModel",
    "TablePreviewWidget",
    "TableWidget",
    "TextAreaWidget",
    "TextFieldWidget",
    "TextViewWidget",
    "make_label",
]
