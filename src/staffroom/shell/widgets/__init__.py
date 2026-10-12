"""The shared widget kit. Every piece of UI a tool can ask for lives here, keyed
by the dataclasses in :mod:`staffroom.core.panel`. New UI needs go here,
never into a tool package."""

from staffroom.shell.widgets.action_table import ActionTableWidget
from staffroom.shell.widgets.bar_chart import BarChartWidget
from staffroom.shell.widgets.card import Card, Divider, make_label
from staffroom.shell.widgets.card_list import CardListWidget
from staffroom.shell.widgets.chip_choice import ChipChoiceWidget
from staffroom.shell.widgets.choice import ChoiceWidget
from staffroom.shell.widgets.code_source import CodeSourceWidget, LineLink
from staffroom.shell.widgets.code_view import CodeViewWidget
from staffroom.shell.widgets.command_box import CommandBox
from staffroom.shell.widgets.compact_table import CompactTableWidget
from staffroom.shell.widgets.first_run import FirstRunCard
from staffroom.shell.widgets.fit_table import FitTable
from staffroom.shell.widgets.image_view import ImageViewWidget
from staffroom.shell.widgets.input_group import InputGroup, eyebrow
from staffroom.shell.widgets.load_summary import FoundWidget, LoadSummaryWidget
from staffroom.shell.widgets.options_form import OptionsFormWidget
from staffroom.shell.widgets.output_pane import OutputPane
from staffroom.shell.widgets.path_picker import PathPickerWidget
from staffroom.shell.widgets.resource_picker import ResourcePickerWidget
from staffroom.shell.widgets.result_strip import ResultStrip
from staffroom.shell.widgets.run_bar import RunBar
from staffroom.shell.widgets.stat_tiles import StatTilesWidget
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
    "BarChartWidget",
    "Card",
    "CardListWidget",
    "ChipChoiceWidget",
    "ChoiceWidget",
    "CodeSourceWidget",
    "CodeViewWidget",
    "CommandBox",
    "CompactTableWidget",
    "Divider",
    "EditableTableWidget",
    "FirstRunCard",
    "FitTable",
    "FoundWidget",
    "ImageViewWidget",
    "InputGroup",
    "LineLink",
    "LoadSummaryWidget",
    "OptionsFormWidget",
    "OutputPane",
    "PathPickerWidget",
    "ResourcePickerWidget",
    "ResultStrip",
    "RunBar",
    "StatTilesWidget",
    "StringListEditor",
    "TableModel",
    "TablePreviewWidget",
    "TableWidget",
    "TextAreaWidget",
    "TextFieldWidget",
    "TextViewWidget",
    "eyebrow",
    "make_label",
]
