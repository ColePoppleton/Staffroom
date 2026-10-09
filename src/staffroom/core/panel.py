"""The declarative panel vocabulary.

A tool describes its UI as data: a :class:`PanelSpec` holding *input* widgets
(things the user fills in) and *output* widgets (things the shell fills from a
:class:`~staffroom.core.plugin.RunResult`). The shell renders these with
its widget kit; tools never see Qt.

Every widget has a ``key``. For inputs, the key names the entry in the
``inputs`` dict handed to ``plugin.run``; for outputs, the key names the entry
of ``RunResult.tables`` / ``RunResult.images`` the shell displays.

Input values by widget type
---------------------------
=================  =====================================================
FilePicker         ``pathlib.Path | None``
FolderPicker       ``pathlib.Path | None``
ResourcePicker     ``pathlib.Path | None`` (from the Resource Library or a dialog)
TextField          ``str``
TextArea           ``str`` (multi-line)
OptionsForm        an instance of the given dataclass
EditableTable      :class:`~staffroom.core.table.Table`
TablePreview       (display only; never appears in ``inputs``)
=================  =====================================================

Output widgets fill from a ``RunResult``: ``ResultsTable`` and
``ActionTable`` from ``tables[key]``, ``ImageView`` from ``images[key]``,
``TextView`` from ``texts[key]``. An ``ActionTable`` additionally lets the
user pick a row and press an action button; the shell then calls
``plugin.act(action_name, row, ctx)`` and applies the returned RunResult.

Under the inputs, the run bar says where the next run will write: the shared
output folder (``Config.output_dir_for``) unless the panel sets ``writes_to``
to a :class:`WritesTo` naming its own destination.

If a new tool needs a widget that is not here, add it here and to the shell's
widget kit. Do not put UI code in a tool.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from staffroom.core.table import Cell

if TYPE_CHECKING:
    from staffroom.core.config import Config

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
class ResourcePicker:
    """Pick a file from the Resource Library (or any file via a dialog when
    the library is unavailable). ``filter_ext`` like ``".py"`` narrows the
    library list; None allows any kind."""

    key: str
    label: str
    filter_ext: str | None = None
    help: str = ""
    required: bool = True


@dataclass(frozen=True)
class TextField:
    """One short line of free text."""

    key: str
    label: str
    placeholder: str = ""
    help: str = ""
    max_length: int = 80
    required: bool = True


@dataclass(frozen=True)
class TextArea:
    """Several lines of free text, e.g. pasted code. Value is ``str``."""

    key: str
    label: str
    placeholder: str = ""
    help: str = ""
    monospace: bool = True
    required: bool = False
    rows: int = 10


@dataclass(frozen=True)
class OptionsPreset:
    """A named set of field values an :class:`OptionsForm` applies in one go.

    ``values`` pins some of the schema's fields; the others keep whatever the
    user has set. The form's Preset dropdown shows the first preset whose
    pinned fields all equal the current values, or "Custom" when none does,
    and the same rule (:func:`matching_preset`) lets a tool print the preset's
    name on its output, so a sheet says which preset it came from even when
    the options were typed on the command line. Build one with :func:`preset`.
    """

    name: str
    values: tuple[tuple[str, Any], ...]

    def matches(self, options: object) -> bool:
        return all(getattr(options, name) == value for name, value in self.values)


def preset(name: str, **values: Any) -> OptionsPreset:
    """``preset("Year 9", top_level_only=True)``: an :class:`OptionsPreset`."""
    return OptionsPreset(name, tuple(values.items()))


def matching_preset(presets: tuple[OptionsPreset, ...], options: object) -> OptionsPreset | None:
    """The first preset whose pinned fields all match ``options``, if any."""
    return next((p for p in presets if p.matches(options)), None)


@dataclass(frozen=True)
class OptionsForm:
    """A form generated from a dataclass. Field types drive the widgets:
    ``bool`` -> checkbox, ``int``/``float`` -> spin box, ``str`` -> line edit,
    ``Literal[...]`` or ``Enum`` -> combo box. Field ``metadata`` may carry
    ``label``, ``help``, ``min``, ``max`` and ``step``.

    ``presets`` adds a Preset dropdown above the fields: choosing one sets the
    fields it pins (see :class:`OptionsPreset`); editing a field afterwards
    moves the dropdown back to whichever preset still matches, or "Custom"."""

    key: str
    schema: type
    label: str = "Options"
    presets: tuple[OptionsPreset, ...] = ()


@dataclass(frozen=True)
class Column:
    name: str
    kind: CellKind = "text"
    width: int | None = None


PresetRows = tuple[tuple[Cell, ...], ...]


@dataclass(frozen=True)
class EditableTable:
    """A small grid the user can edit, e.g. grade boundaries.

    ``presets`` are named row sets the user can apply from a dropdown. If
    ``preset_action`` is set, "Save as preset" calls
    ``plugin.act(preset_action, {"name": str, "table": Table}, ctx)`` so the
    plugin can persist it (usually in ``config.tool(name)``)."""

    key: str
    label: str
    columns: tuple[Column, ...]
    rows: tuple[tuple[Cell, ...], ...] = ()
    can_add_rows: bool = True
    help: str = ""
    presets: tuple[tuple[str, PresetRows], ...] = ()
    preset_action: str | None = None


@dataclass(frozen=True)
class TablePreview:
    """Read-only preview of the table behind a FilePicker (by its key)."""

    key: str
    source: str
    label: str = "Preview"
    max_rows: int = 200


InputWidget = (
    FilePicker
    | FolderPicker
    | ResourcePicker
    | TextField
    | TextArea
    | OptionsForm
    | EditableTable
    | TablePreview
)


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
class TextView:
    """A read-only block of text (``RunResult.texts[key]``), e.g. a diff.
    ``copy_button`` adds a Copy button that puts the text on the clipboard."""

    key: str
    label: str = "Output"
    monospace: bool = True
    copy_button: bool = False


@dataclass(frozen=True)
class Action:
    name: str
    label: str
    help: str = ""
    primary: bool = False


@dataclass(frozen=True)
class ActionTable:
    """A table whose rows can be acted on. ``refresh_action`` is called with
    an empty row when the panel is shown and after every run or action, so
    the table reflects the world (e.g. past sessions on disk)."""

    key: str
    label: str
    actions: tuple[Action, ...]
    refresh_action: str | None = None
    hidden_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class LogArea:
    key: str = "log"
    label: str = "Log"


OutputWidget = ResultsTable | ActionTable | ImageView | TextView | LogArea


# ---------------------------------------------------------------- destination
DEFAULT_WRITES_VERB = "Writes to"
DEFAULT_OPEN_LABEL = "Open output folder"


@dataclass(frozen=True)
class WritesTo:
    """Where a run's files land, for a tool that does not write to the shared
    output folder (e.g. classroom copies into the sessions folder).

    ``folder(inputs, config)`` returns the folder the next run will write to,
    from the same ``inputs`` dict ``plugin.run`` gets. It only computes a path:
    no file access, it must not raise, and it is called on every input change.
    The shell shows ``"<verb> <folder>"`` beside the Run button and a link
    labelled ``open_label`` that opens the folder (creating it if need be)."""

    folder: Callable[[Mapping[str, Any], Config], Path]
    verb: str = DEFAULT_WRITES_VERB
    open_label: str = DEFAULT_OPEN_LABEL


# ---------------------------------------------------------------- the panel
@dataclass(frozen=True)
class PanelSpec:
    title: str
    description: str = ""
    inputs: tuple[InputWidget, ...] = ()
    outputs: tuple[OutputWidget, ...] = field(default=(LogArea(),))
    run_label: str = "Run"
    writes_to: WritesTo | None = None  # None: the shared output folder

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
            if isinstance(w, OptionsForm) and w.presets:
                names = {f.name for f in dataclasses.fields(w.schema)}
                for p in w.presets:
                    unknown = sorted(set(dict(p.values)) - names)
                    if unknown:
                        msg = (
                            f"preset {p.name!r} of OptionsForm {w.key!r} pins fields "
                            f"{unknown} that {w.schema.__name__} does not have"
                        )
                        raise ValueError(msg)

    def input_keys(self) -> list[str]:
        return [w.key for w in self.inputs if not isinstance(w, TablePreview)]

    def refresh_actions(self) -> list[str]:
        return [
            w.refresh_action
            for w in self.outputs
            if isinstance(w, ActionTable) and w.refresh_action is not None
        ]
