"""Which file types each tool takes, read from its own panel spec (#88):
the Library's use bar is built from this."""

from __future__ import annotations

from staffroom.core.discovery import discover_plugins, visible_plugins
from staffroom.core.panel import (
    FileInput,
    FilePicker,
    PanelSpec,
    ResourcePicker,
    TextField,
    filter_extensions,
    main_file_input,
    normalise_extensions,
    tools_accepting,
)


def test_filter_extensions_reads_dialog_filters() -> None:
    assert filter_extensions(("Data files (*.csv *.xlsx)", "All files (*)")) == (".csv", ".xlsx")
    assert filter_extensions(("CSV files (*.CSV)",)) == (".csv",)
    assert filter_extensions(("All files (*)",)) == ()


def test_resource_picker_takes_one_or_several_extensions() -> None:
    assert ResourcePicker("k", "K", filter_ext=".PY").extensions == (".py",)
    assert ResourcePicker("k", "K", filter_ext=("py", ".txt", ".py")).extensions == (".py", ".txt")
    assert ResourcePicker("k", "K").extensions == ()
    assert normalise_extensions(None) == ()


def test_main_file_input_is_the_first_file_picker_that_opens() -> None:
    spec = PanelSpec(
        title="T",
        inputs=(
            TextField("label", "Label"),
            FilePicker("out", "Save as", mode="save", filters=("PDF (*.pdf)",)),
            FilePicker("data", "Data"),
            ResourcePicker("other", "Other", filter_ext=".md"),
        ),
    )
    assert main_file_input(spec) == FileInput("data", (".csv", ".xlsx"))
    assert main_file_input(PanelSpec(title="None")) is None


def test_file_input_accepts_by_last_suffix() -> None:
    code = FileInput("source", (".py", ".txt"))
    assert code.accepts("loops.py") and code.accepts("loops.ocr.txt") and code.accepts("A.PY")
    assert not code.accepts("slides.pptx")
    assert FileInput("resource", ()).accepts("anything.bin")


def test_tools_accepting_leaves_out_any_file_tools() -> None:
    inputs = {
        "classroom": FileInput("resource", ()),
        "worksheet": None,
        "parsons": FileInput("source", (".py",)),
        "pseudocode": FileInput("source", (".py", ".txt")),
    }
    assert tools_accepting(inputs, "a.py") == ["parsons", "pseudocode"]
    assert tools_accepting(inputs, "a.txt") == ["pseudocode"]
    assert tools_accepting(inputs, "a.docx") == []


def test_the_installed_tools_declare_what_the_issue_lists() -> None:
    """``.py`` → the five code tools, ``.md`` → Quiz, ``.csv`` / ``.xlsx`` → Marks."""
    inputs = {p.name: main_file_input(p.panel_spec()) for p in visible_plugins(discover_plugins())}
    assert set(tools_accepting(inputs, "x.py")) == {
        "parsons",
        "trace",
        "bugs",
        "fade",
        "pseudocode",
    }
    assert tools_accepting(inputs, "x.md") == ["quiz"]
    assert tools_accepting(inputs, "x.csv") == tools_accepting(inputs, "x.xlsx") == ["marks"]
    assert "hello" not in inputs  # hidden
