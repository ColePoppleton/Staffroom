"""The declarative panel vocabulary.

A tool describes its UI as data: a :class:`PanelSpec` holding *input* widgets
(things the user fills in) and *output* widgets (things the shell fills from a
:class:`~teaching_tools.core.plugin.RunResult`). The shell renders these with
its widget kit; tools never see Qt.

Every widget has a ``key``. For inputs, the key names the entry in the
``inputs`` dict handed to ``plugin.run``; for outputs, the key names the entry
of ``RunResult.tables`` / ``RunResult.images`` the shell displays.

Input values by widget type
---------------------------
=================  =====================================================
FilePicker         ``pathlib.Path | None``
FolderPicker       ``pathlib.Path | None``
OptionsForm        an instance of the given dataclass
EditableTable      :class:`~teaching_tools.core.table.Table`
TablePreview       (display only; never appears in ``inputs``)
=================  =====================================================

If a new tool needs a widget that is not here, add it here and to the shell's
widget kit. Do not put UI code in a tool.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from teaching_tools.core.table import Cell

CellKind = Literal["text", "int", "float", "bool"]


# ---------------------------------------------------------------- inputs
@dataclass(frozen=True)
class FilePicker:
    key: str
    label: str
    filters: tuple[str, ...] = ("Data files (*.csv *.xlsx)", "All files (*)")
    mode: Literal["open", "save"] = "open"
    help: str = ""
    required: bool = True


@dataclass(frozen=True)
class FolderPicker:
    key: str
    label: str
    help: str = ""
    required: bool = False


@dataclass(frozen=True)
class OptionsForm:
    """A form generated from a dataclass. Field types drive the widgets:
    ``bool`` -> checkbox, ``int``/``float`` -> spin box, ``str`` -> line edit,
    ``Literal[...]`` or ``Enum`` -> combo box. Field ``metadata`` may carry
    ``label``, ``help``, ``min``, ``max`` and ``step``."""

    key: str
    schema: type
    label: str = "Options"


@dataclass(frozen=True)
class Column:
    name: str
    kind: CellKind = "text"
    width: int | None = None


@dataclass(frozen=True)
class EditableTable:
    """A small grid the user can edit, e.g. grade boundaries."""

    key: str
    label: str
    columns: tuple[Column, ...]
    rows: tuple[tuple[Cell, ...], ...] = ()
    can_add_rows: bool = True
    help: str = ""


@dataclass(frozen=True)
class TablePreview:
    """Read-only preview of the table behind a FilePicker (by its key)."""

    key: str
    source: str
    label: str = "Preview"
    max_rows: int = 200


InputWidget = FilePicker | FolderPicker | OptionsForm | EditableTable | TablePreview


# ---------------------------------------------------------------- outputs
@dataclass(frozen=True)
class ResultsTable:
    key: str
    label: str = "Results"


@dataclass(frozen=True)
class ImageView:
    """Shows a PNG produced by the run (``RunResult.images[key]``)."""

    key: str
    label: str = "Chart"


@dataclass(frozen=True)
class LogArea:
    key: str = "log"
    label: str = "Log"


OutputWidget = ResultsTable | ImageView | LogArea


# ---------------------------------------------------------------- the panel
@dataclass(frozen=True)
class PanelSpec:
    title: str
    description: str = ""
    inputs: tuple[InputWidget, ...] = ()
    outputs: tuple[OutputWidget, ...] = field(default=(LogArea(),))
    run_label: str = "Run"

    def __post_init__(self) -> None:
        keys = [w.key for w in self.inputs] + [w.key for w in self.outputs]
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            msg = f"duplicate widget keys in panel {self.title!r}: {sorted(dupes)}"
            raise ValueError(msg)
        sources = {w.key for w in self.inputs if isinstance(w, FilePicker)}
        for w in self.inputs:
            if isinstance(w, TablePreview) and w.source not in sources:
                msg = f"TablePreview {w.key!r} refers to unknown FilePicker {w.source!r}"
                raise ValueError(msg)

    def input_keys(self) -> list[str]:
        return [w.key for w in self.inputs if not isinstance(w, TablePreview)]
