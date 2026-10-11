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
CodeSource         :class:`CodeValue` ``(path, text)``: the file shown, or pasted
                   text with ``path`` None (and its ``choice``, if any, under
                   the choice's own key). Turn it into source text with
                   :func:`staffroom.core.codeinput.code_from_inputs`.
TextField          ``str``
TextArea           ``str`` (multi-line)
Choice             ``str`` (the chosen value)
ChipChoice         ``tuple[str, ...]`` (the values of the chips that are on)
OptionsForm        an instance of the given dataclass
EditableTable      :class:`~staffroom.core.table.Table` (and its ``choice``, if
                   any, under the choice's own key)
TablePreview       (display only; never appears in ``inputs``)
=================  =====================================================

Output widgets fill from a ``RunResult``: ``ResultsTable``, ``CardList``, ``ActionTable``,
``StatTiles`` (build its table with :func:`stat_table`) and ``BarChart`` from
``tables[key]``, ``ImageView`` from ``images[key]``, ``TextView`` from
``texts[key]`` (and a ``BarChart`` takes a one-line caption from there),
``PagePreview`` from ``pages[key]`` (build its :class:`Pages` with
:func:`pages_from` over the files the run wrote). A
``ResultsTable`` with ``line_column`` points its rows at lines of the panel's
``CodeSource``: selecting a row lights its line, clicking a line selects its
rows (a ``CardList`` links its cards the same way). A wide ``ResultsTable``
can be made to fit the screen with ``compact``, ``lift_constants``,
``mark_changes`` and ``pin_last``. An
``ActionTable`` additionally lets the user pick a row and press an action
button; the shell then calls
``plugin.act(action_name, row, ctx)`` and applies the returned RunResult.

Layout (the workbench)
----------------------
The shell lays every panel out the same way: the inputs in a column on the
left with the run button at its foot, the outputs filling the right. Outputs
are either *main* views (the reason for the visit: a table, a chart, a
preview; more than one becomes tabs, or sits side by side with
``PanelSpec.main_layout="row"``; a ``PagePreview`` is two tabs, *Sheet* and
*Key*), *top* (a headline over the main view, such
as ``StatTiles``) or *below* (secondary: lists to act on, notes, a folded
detail table), stacked under the main view. :func:`top_outputs`,
:func:`main_outputs` and :func:`below_outputs` decide, from each widget's
optional ``place`` hint: ``StatTiles`` defaults to top, ``ActionTable`` to
below, everything else to main, and a panel with no main view promotes its
first output. ``LogArea`` is none of these: the run log sits behind a
one-line *Details* toggle at the foot of the output pane (every panel has one;
listing ``LogArea`` is optional and changes nothing).

How a run went is not a widget a tool declares: the shell's result strip, on
top of the output pane, shows ``RunResult.outcome`` (or ``summary``), one
button per file in ``RunResult.files`` and the warnings raised with
``RunContext.warn``. A failed run shows the ``ToolError``'s message there; the
error's ``next_step`` takes the output pane's place (else the pane is empty),
and its ``input_key`` marks the input to fix, with ``input_hint`` under it
(see :class:`staffroom.core.plugin.ToolError`).

Under the run button, the shell says where the next run will write: the
shared output folder (``Config.output_dir_for``) unless the panel sets
``writes_to`` to a :class:`WritesTo` naming its own destination.

An ``OptionsForm`` can hide fields that do not apply (``shown_when``), name
its choices in words (``choice_labels``) and draw a short choice as a
segmented switch (``switches``); see :class:`OptionsForm`. A whole input can
hide the same way: ``PanelSpec.shown_when`` maps an input's key to the
condition under which it applies, read from a field of an options form
(``"options.retrieval"``) or a ``Choice``; see :class:`PanelSpec`.

A panel's ``inspect`` says what the tool found in its inputs while the
teacher fills them in: a load summary under a file, the chips of a
:class:`ChipChoice` taken from it (a bank's topics, with counts), the run
button's words; see :class:`PanelSpec`. ``joined`` draws an input as part of
the group above it.

A panel's ``suggest`` lets a choice follow the code or file picked (e.g.
pseudocode's *From* shows the language it guessed): a pure function from the
current inputs to new values for ``Choice`` keys, called whenever a file is
picked or code is pasted.

If a new tool needs a widget that is not here, add it here and to the shell's
widget kit. Do not put UI code in a tool.
"""

from __future__ import annotations

import dataclasses
import enum
import re
import string
import types
import typing
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple

from staffroom.core.table import Cell, Table

if TYPE_CHECKING:
    from staffroom.core.config import Config

CellKind = Literal["text", "int", "float", "bool"]


# ---------------------------------------------------------------- inputs
@dataclass(frozen=True)
class FilePicker:
    """Choose a file. ``chip`` shows the chosen file as a chip (its type, its
    name, a Change button; the full path in the tooltip) instead of a path
    field: for an input that is read, not typed."""

    key: str
    label: str
    filters: tuple[str, ...] = ("Data files (*.csv *.xlsx)", "All files (*)")
    mode: Literal["open", "save"] = "open"
    help: str = ""
    required: bool = True
    chip: bool = False

    @property
    def extensions(self) -> tuple[str, ...]:
        """The extensions ``filters`` names (see :func:`filter_extensions`)."""
        return filter_extensions(self.filters)


def normalise_extensions(exts: str | Iterable[str] | None) -> tuple[str, ...]:
    """``".PY"``, ``("py", ".txt")`` or None as lower-case extensions with the
    dot, without repeats; () (any file) for None."""
    if exts is None:
        return ()
    out: list[str] = []
    for ext in (exts,) if isinstance(exts, str) else exts:
        e = ext.strip().lower()
        e = e if e.startswith(".") else f".{e}"
        if e != "." and e not in out:
            out.append(e)
    return tuple(out)


_FILTER_PATTERN = re.compile(r"\*(\.[A-Za-z0-9]+)")


def filter_extensions(filters: Iterable[str]) -> tuple[str, ...]:
    """The extensions named in Qt file-dialog filters: ``("Data files (*.csv
    *.xlsx)", "All files (*)")`` gives ``(".csv", ".xlsx")``. A catch-all
    ``*`` adds nothing; no ``*.ext`` anywhere gives () (any file)."""
    return normalise_extensions(m.group(1) for f in filters for m in _FILTER_PATTERN.finditer(f))


@dataclass(frozen=True)
class FolderPicker:
    key: str
    label: str
    help: str = ""
    required: bool = False


@dataclass(frozen=True)
class ResourcePicker:
    """Pick a file from the Resource Library (or any file via a dialog when
    the library is unavailable). ``filter_ext`` like ``".py"`` (or several,
    ``(".py", ".txt")``) narrows the library list; None allows any kind.

    The same extensions put the tool on the Library's use bar for files of
    that type (see :func:`main_file_input`).

    ``chip`` shows the chosen file as a chip, as a :class:`CodeSource` does:
    its type, its name and its folder (the library folder for a library
    file; the full path in the tooltip) and *Change ▾*, with *From library…*
    and *Browse…* before a file is chosen. What the tool found in the file
    (``PanelSpec.inspect``) shows under it."""

    key: str
    label: str
    filter_ext: str | tuple[str, ...] | None = None
    help: str = ""
    required: bool = True
    chip: bool = False

    @property
    def extensions(self) -> tuple[str, ...]:
        """``filter_ext`` as lower-case extensions with the dot; () for any file."""
        return normalise_extensions(self.filter_ext)


class CodeValue(NamedTuple):
    """A :class:`CodeSource`'s value: the file chosen (``path``) and the text
    shown, or ``path`` None and the text pasted."""

    path: Path | None
    text: str


@dataclass(frozen=True)
class CodeSource:
    """The program a code tool works on, in one input: a chip naming the file
    (from the Resource Library or a dialog; *Change ▾*) over a read-only,
    highlighted view of it with line numbers, or *Paste instead* for text
    that is in no file. Value: :class:`CodeValue`.

    It shows code and accepts a paste; it is not an editor (Thonny is).
    ``choice`` adds a :class:`Choice` between the chip and the code, for a
    setting about the code itself (e.g. the language it is in); its value
    reaches the tool under the choice's own key."""

    key: str
    label: str = "Program"
    filter_ext: str | tuple[str, ...] | None = ".py"
    help: str = ""
    required: bool = True
    choice: Choice | None = None

    @property
    def extensions(self) -> tuple[str, ...]:
        """``filter_ext`` as lower-case extensions with the dot; () for any file.
        They also put the tool on the Library's use bar (:func:`main_file_input`)."""
        return normalise_extensions(self.filter_ext)


@dataclass(frozen=True)
class TextField:
    """One short line of free text. ``counter`` shows how much of
    ``max_length`` is used (a label that must fit); off for a value of a
    known shape, such as a date."""

    key: str
    label: str
    placeholder: str = ""
    help: str = ""
    max_length: int = 80
    required: bool = True
    counter: bool = True


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
class Choice:
    """One of a few exclusive values, shown as a segmented switch. ``choices``
    are ``(value, text)`` pairs; the value handed to the tool is the chosen
    ``value`` (``default``, or the first one, until the user picks)."""

    key: str
    label: str
    choices: tuple[tuple[str, str], ...]
    default: str | None = None
    help: str = ""

    def __post_init__(self) -> None:
        values = [v for v, _ in self.choices]
        if not values or (self.default is not None and self.default not in values):
            msg = f"Choice {self.key!r} needs choices that include its default"
            raise ValueError(msg)

    @property
    def initial(self) -> str:
        return self.default if self.default is not None else self.choices[0][0]


@dataclass(frozen=True)
class ChipOption:
    """One chip of a :class:`ChipChoice`: the ``value`` handed to the tool,
    the ``text`` shown (the value itself when empty) and an optional
    ``count`` shown small after it (how many questions carry the topic)."""

    value: str
    text: str = ""
    count: int | None = None

    @property
    def shown(self) -> str:
        return self.text or self.value


@dataclass(frozen=True)
class ChipChoice:
    """Toggle chips, any number on at once: the topics of a question bank.
    Value: the ``value`` of each chip that is on, in chip order, as a tuple;
    ``()`` when none is (a tool reads that as "no filter", and says so).

    ``options`` are the chips when they are fixed. Usually they come from a
    file the teacher picked: ``PanelSpec.inspect`` returns them as
    ``Found(chips=...)`` for this key whenever the inputs change, and the
    chips that are on stay on while the new options still have them.
    ``empty_text`` shows while there are no chips ("Choose a bank to see its
    topics"); the notes ``inspect`` returns for this key show under the chips
    (a running total)."""

    key: str
    label: str
    options: tuple[ChipOption, ...] = ()
    help: str = ""
    empty_text: str = ""


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


# The labels for the ``formats`` field the sheet tools share
# (``Literal["both", "docx", "pdf"]``): what the teacher reads, not the value.
OUTPUT_FORMAT_LABELS: Mapping[str, str] = {"both": "Word + PDF", "docx": "Word", "pdf": "PDF"}


@dataclass(frozen=True)
class ShownWhen:
    """Show an :class:`OptionsForm` field only while the field ``on`` holds one
    of ``values`` (and is itself shown). Build one with :func:`shown_when`.

    In ``PanelSpec.shown_when`` (a whole input) ``on`` names what the
    condition reads across the panel: ``"<form key>.<field>"`` for a field of
    one of its options forms, or the key of a :class:`Choice`."""

    on: str
    values: tuple[Any, ...]


def shown_when(on: str, *values: Any) -> ShownWhen:
    """``shown_when("topic", "truth_tables")``: a :class:`ShownWhen`. For a
    whole input, ``shown_when("options.retrieval", True)``."""
    if not values:
        msg = f"shown_when({on!r}) needs at least one value"
        raise ValueError(msg)
    return ShownWhen(on, values)


def hidden_fields(conditions: Mapping[str, ShownWhen], options: object) -> frozenset[str]:
    """The fields whose condition does not hold for ``options``, or whose
    condition depends on a field that is itself hidden."""

    def hidden(name: str) -> bool:
        cond = conditions.get(name)
        if cond is None:
            return False
        return hidden(cond.on) or getattr(options, cond.on) not in cond.values

    return frozenset(name for name in conditions if hidden(name))


def choice_values(schema: type, name: str) -> tuple[Any, ...] | None:
    """The values a ``Literal[...]`` or ``Enum`` field of ``schema`` can take
    (``Optional`` unwrapped), or None for any other field type."""
    hint = typing.get_type_hints(schema)[name]
    if typing.get_origin(hint) in (typing.Union, types.UnionType):
        hint = next(a for a in typing.get_args(hint) if a is not type(None))
    if typing.get_origin(hint) is Literal:
        return typing.get_args(hint)
    if isinstance(hint, type) and issubclass(hint, enum.Enum):
        return tuple(hint)
    return None


def choice_key(value: Any) -> str:
    """How a choice value is keyed in ``OptionsForm.choice_labels``: an
    ``Enum`` member by its value, anything else as itself, both as text."""
    return str(value.value) if isinstance(value, enum.Enum) else str(value)


@dataclass(frozen=True)
class OptionsForm:
    """A form generated from a dataclass. Field types drive the widgets:
    ``bool`` -> checkbox, ``int``/``float`` -> spin box, ``str`` -> line edit,
    ``Literal[...]`` or ``Enum`` -> combo box. Field ``metadata`` may carry
    ``label``, ``help``, ``min``, ``max`` and ``step``.

    ``presets`` adds a Preset dropdown above the fields: choosing one sets the
    fields it pins (see :class:`OptionsPreset`); editing a field afterwards
    moves the dropdown back to whichever preset still matches, or "Custom".

    ``fields`` limits the form to the named fields (empty: all of them); the
    rest keep their dataclass defaults, e.g. one a :class:`Choice` sets.

    ``shown_when`` maps a field to the :class:`ShownWhen` under which it
    applies (``{"laws": shown_when("topic", "boolean_simplification")}``); the
    form hides it otherwise. A hidden field keeps what the teacher set in the
    form, so it comes back unchanged when it applies again, but the tool is
    handed the field's default (:meth:`passed`): a value the teacher cannot
    see never changes, or breaks, a run, and the tool gets exactly what the
    command line gives it when the flag is left out.

    ``choice_labels`` maps a choice field (``Literal`` or ``Enum``) to the text
    shown for each value (``{"formats": OUTPUT_FORMAT_LABELS}``); a value with
    no label shows as itself. ``switches`` names choice fields drawn as a
    segmented switch instead of a dropdown: keep those to two to four short
    labels (Easy / Medium / Hard).

    ``inline`` names fields drawn side by side on one row, under the first
    one's label, each after its own (two or three short numbers: *Questions*
    and *Seed*); they always show. ``more`` names fields folded behind a
    *More* link at the foot of the form, for what few runs need (a spec-point
    filter); the link opens them, and they open by themselves while one of
    them holds a value other than its default, so nothing that steers a run
    is out of sight."""

    key: str
    schema: type
    label: str = "Options"
    presets: tuple[OptionsPreset, ...] = ()
    fields: tuple[str, ...] = ()
    shown_when: Mapping[str, ShownWhen] = field(default_factory=dict)
    choice_labels: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    switches: tuple[str, ...] = ()
    inline: tuple[str, ...] = ()
    more: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not dataclasses.is_dataclass(self.schema):
            return  # the shell says so when it builds the form
        names = {f.name for f in dataclasses.fields(self.schema)}
        in_form = set(self.fields) or names

        def check(where: str, name: str) -> None:
            if name not in names:
                msg = f"OptionsForm {self.key!r}: {where} names {name!r}, not a field"
                raise ValueError(msg)
            if name not in in_form:
                msg = f"OptionsForm {self.key!r}: {where} names {name!r}, not in its fields"
                raise ValueError(msg)

        for name, cond in self.shown_when.items():
            check("shown_when", name)
            check(f"shown_when[{name!r}]", cond.on)
            allowed = choice_values(self.schema, cond.on)
            wrong = [v for v in cond.values if allowed is not None and v not in allowed]
            if wrong:
                msg = f"OptionsForm {self.key!r}: {cond.on!r} can never be {wrong}"
                raise ValueError(msg)
        for name in self.shown_when:  # a field may not depend on itself, even by a loop
            seen = [name]
            while (step := self.shown_when.get(seen[-1])) is not None:
                if step.on in seen:
                    msg = f"OptionsForm {self.key!r}: shown_when loops: {[*seen, step.on]}"
                    raise ValueError(msg)
                seen.append(step.on)
        for where, keys in (("choice_labels", self.choice_labels), ("switches", self.switches)):
            for name in keys:
                check(where, name)
                values = choice_values(self.schema, name)
                if values is None:
                    msg = f"OptionsForm {self.key!r}: {where} names {name!r}, not a choice"
                    raise ValueError(msg)
                unknown = sorted(
                    set(self.choice_labels.get(name, {})) - {choice_key(v) for v in values}
                )
                if unknown:
                    msg = f"OptionsForm {self.key!r}: {name!r} labels values it lacks: {unknown}"
                    raise ValueError(msg)
        for where, keys in (("inline", self.inline), ("more", self.more)):
            for name in keys:
                check(where, name)
        if len(self.inline) == 1:
            msg = f"OptionsForm {self.key!r}: inline needs two fields or more, not {self.inline}"
            raise ValueError(msg)
        both = sorted(set(self.inline) & set(self.more))
        if both:
            msg = f"OptionsForm {self.key!r}: {both} cannot be both inline and under More"
            raise ValueError(msg)
        conditional = sorted(set(self.inline) & set(self.shown_when))
        if conditional:
            msg = f"OptionsForm {self.key!r}: inline fields always show; {conditional} do not"
            raise ValueError(msg)

    def hidden(self, options: object) -> frozenset[str]:
        """The fields that do not apply to ``options`` (see ``shown_when``)."""
        return hidden_fields(self.shown_when, options)

    def passed(self, options: Any) -> Any:
        """``options`` as handed to the tool: every hidden field at its default."""
        hidden = self.hidden(options)
        if not hidden:
            return options
        defaults = self.schema()
        return dataclasses.replace(options, **{n: getattr(defaults, n) for n in hidden})

    def label_for(self, name: str, value: Any) -> str:
        """The text shown for one value of the choice field ``name``."""
        key = choice_key(value)
        return self.choice_labels.get(name, {}).get(key, key)


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
    plugin can persist it (usually in ``config.tool(name)``).

    ``compact`` draws a two-column (label, number) table as a grid of small
    cells, ``per_row`` to a line, each label beside its editable number: ten
    grade boundaries in two lines instead of a ten-row table. Choosing a preset
    applies it at once; rows are not added or removed.

    ``choice`` adds a :class:`Choice` between the preset and the grid, for a
    setting that says how to read the numbers (e.g. % of the paper or raw
    marks). Its value reaches the tool under the choice's own key."""

    key: str
    label: str
    columns: tuple[Column, ...]
    rows: tuple[tuple[Cell, ...], ...] = ()
    can_add_rows: bool = True
    help: str = ""
    presets: tuple[tuple[str, PresetRows], ...] = ()
    preset_action: str | None = None
    compact: bool = False
    per_row: int = 5
    choice: Choice | None = None


@dataclass(frozen=True)
class Note:
    """One line of a load summary: ``ok`` lines get a tick, the others a warning mark."""

    text: str
    ok: bool = True


@dataclass(frozen=True)
class TablePreview:
    """Read-only preview of the table behind a FilePicker (by its key).

    ``flag`` is passed to ``core.csvio.read_table`` (e.g. ``"MAX"``) so the
    preview sees the same flagged rows the tool will. ``summary`` turns the
    loaded table into a few :class:`Note` lines (what was found, what was
    dropped); it is pure and called on every file change.

    ``compact`` shows only the summary, under the file picker in the same
    group, with a *Preview rows* link that opens the rows on demand, instead
    of a table of rows in its own group."""

    key: str
    source: str
    label: str = "Preview"
    max_rows: int = 200
    flag: str | None = None
    summary: Callable[[Table], Sequence[Note]] | None = None
    compact: bool = False


InputWidget = (
    FilePicker
    | FolderPicker
    | ResourcePicker
    | CodeSource
    | TextField
    | TextArea
    | Choice
    | ChipChoice
    | OptionsForm
    | EditableTable
    | TablePreview
)


def empty_values(widget: InputWidget) -> dict[str, Any]:
    """What ``widget`` hands the tool before the teacher touches it, by key:
    no file, no text, a choice's initial value, a form's dataclass defaults,
    a grid's own rows. A hidden input hands over this (see
    ``PanelSpec.shown_when``); a :class:`TablePreview` hands over nothing."""
    if isinstance(widget, FilePicker | FolderPicker | ResourcePicker):
        return {widget.key: None}
    if isinstance(widget, TextField | TextArea):
        return {widget.key: ""}
    if isinstance(widget, Choice):
        return {widget.key: widget.initial}
    if isinstance(widget, ChipChoice):
        return {widget.key: ()}
    if isinstance(widget, OptionsForm):
        return {widget.key: widget.schema()}
    if isinstance(widget, CodeSource | EditableTable):
        value: Any = (
            CodeValue(None, "")
            if isinstance(widget, CodeSource)
            else Table([c.name for c in widget.columns], [list(r) for r in widget.rows])
        )
        inner = {} if widget.choice is None else {widget.choice.key: widget.choice.initial}
        return {widget.key: value, **inner}
    return {}


# ---------------------------------------------------------------- outputs
Place = Literal["top", "main", "below"]
"""Where an output sits in the output pane: ``"top"`` (a headline over the
main view), a ``"main"`` view (tabs when there are several, or side by side
with ``PanelSpec.main_layout="row"``) or ``"below"`` the main view. ``None``
lets the shell choose."""


@dataclass(frozen=True)
class BarColumn:
    """A numeric column drawn with an inline bar beside its number, the bar
    full at ``maximum`` (e.g. a facility index from 0 to 1)."""

    name: str
    maximum: float = 1.0


@dataclass(frozen=True)
class ResultsTable:
    """A read-only table from ``tables[key]``.

    ``bars`` draws the named numeric columns with an inline bar.
    ``tag_column``'s non-empty text is shown as a small tag beside the first
    cell of its row (e.g. "reteach") as a call to action, in the accent
    colour with the row's bars; the column itself is not shown. ``hidden_columns`` are not shown
    either; their values appear in the row's tooltip instead.

    ``collapsed`` (for a ``"below"`` table) starts folded: only its label and
    row count show until the user opens it.

    ``line_column`` names a column of line numbers in the program of the
    panel's :class:`CodeSource` ``line_source``: selecting a row lights its
    line in the code, and clicking a line selects the rows that point at it
    (a trace table's steps, a bug key's variants).

    For a wide table that must fit the screen (a completed trace table), four
    options change only how it is shown, never the table the tool returns:

    * ``compact``: columns as narrow as their header and widest value, not the
      roomy default; a value too long for its column shows in full as a tooltip.
    * ``lift_constants``: a column whose value never changes once set, and
      which repeats on at least half the rows, leaves the table for one line
      above it ("Never changes after line 2: scores = [45, 62, 58]"); see
      :func:`constant_columns`.
    * ``mark_changes``: a value is bold on the row where it differs from the
      row above and grey where it is carried down (the trace-table convention;
      see :func:`change_marks`). The line column and a pinned column stay plain.
    * ``pin_last``: the last column stays in view at the right edge however
      wide the rest (a trace's *Output*); the others scroll sideways under
      it if they must."""

    key: str
    label: str = "Results"
    place: Place | None = None
    bars: tuple[BarColumn, ...] = ()
    tag_column: str | None = None
    hidden_columns: tuple[str, ...] = ()
    collapsed: bool = False
    line_column: str | None = None
    line_source: str = "source"
    compact: bool = False
    lift_constants: bool = False
    mark_changes: bool = False
    pin_last: bool = False

    def plain_columns(self, table: Table) -> tuple[str, ...]:
        """Columns that are never lifted or marked: the line column, the
        pinned last column, hidden and tag columns, bars."""
        plain = {*self.hidden_columns, *(b.name for b in self.bars)}
        plain |= {c for c in (self.line_column, self.tag_column) if c}
        if self.pin_last and table.columns:
            plain.add(table.columns[-1])
        return tuple(c for c in table.columns if c in plain)


LIFT_SHARE = 0.5  # a constant must repeat on at least this share of the rows to leave the table


def _blank(value: Cell) -> bool:
    return value is None or value == ""


@dataclass(frozen=True)
class Constant:
    """A column lifted out of a table by :func:`constant_columns`: its one
    value, and the line-column value of the row where it was first set
    (None without a line column)."""

    column: str
    value: Cell
    line: Cell = None


def constant_columns(
    table: Table,
    *,
    skip: Iterable[str] = (),
    line_column: str | None = None,
    share: float = LIFT_SHARE,
) -> list[Constant]:
    """The columns of ``table`` (bar ``skip``) whose non-blank values are all
    the same and fill at least ``share`` of the rows (and two rows at least):
    a value that repeats down the table without ever changing, such as a
    list a trace sets on its first line. A value set once near the end (an
    average worked out on the last lines) stays in the table, where its row
    says when it was set."""
    skipped = set(skip)
    lines = table.column(line_column) if line_column in table.columns else None
    found: list[Constant] = []
    for i, name in enumerate(table.columns):
        if name in skipped:
            continue
        filled = [(r, row[i]) for r, row in enumerate(table.rows) if not _blank(row[i])]
        if len(filled) < max(2, share * len(table.rows)):
            continue
        first_row, value = filled[0]
        if any(v != value for _r, v in filled):
            continue
        found.append(Constant(name, value, lines[first_row] if lines is not None else None))
    return found


def change_marks(table: Table, *, skip: Iterable[str] = ()) -> list[list[bool | None]]:
    """Per row, per column: True where the value differs from the row above
    (it changed on this row), False where it is the same (carried down), None
    for a blank cell or a column in ``skip``."""
    skipped = {i for i, name in enumerate(table.columns) if name in set(skip)}
    marks: list[list[bool | None]] = []
    previous: list[Cell] = [None] * len(table.columns)
    for row in table.rows:
        line: list[bool | None] = []
        for i, value in enumerate(row):
            if i in skipped or _blank(value):
                line.append(None)
            else:
                line.append(value != previous[i])
        marks.append(line)
        previous = list(row)
    return marks


Tone = Literal["neutral", "warning", "danger"]
"""How loudly a :class:`CardList` badge speaks: ``"danger"`` (it breaks),
``"warning"`` (it goes wrong quietly) or ``"neutral"``."""


@dataclass(frozen=True)
class CardList:
    """One card per row of ``tables[key]``: for a short list whose rows each
    say several things that a table would spread past the right edge (a bug
    key: which version, where, what kind, the old and new line, what happens).

    Every card shows, in order:

    * a heading: ``title`` in bold, then each of ``details`` in muted text,
      and ``badge``'s value as a badge at the right, coloured by ``tones``
      (value of ``tone_column`` -> :data:`Tone`; anything else is neutral).
      ``title`` and ``details`` are format strings over the row's columns,
      e.g. ``"Version {Version}"`` (a blank cell is left out with its text);
    * ``code_lines``: ``(caption, column)`` pairs shown as code under the
      heading, the first muted and the rest on a tinted ground, as in a diff
      (``("was", "Original"), ("now", "Changed to")``).

    The badge is never cut: the heading's other text wraps first. Columns
    the cards do not name are not shown. ``line_column`` / ``line_source``
    link cards to lines of the code as a :class:`ResultsTable` does: a
    selected card (click, or the arrow keys) lights its line, and clicking a
    line selects its cards."""

    key: str
    label: str = "Results"
    title: str = ""
    details: tuple[str, ...] = ()
    badge: str | None = None
    tone_column: str | None = None
    tones: tuple[tuple[str, Tone], ...] = ()
    code_lines: tuple[tuple[str, str], ...] = ()
    line_column: str | None = None
    line_source: str = "source"
    place: Place | None = None

    def tone(self, value: Cell) -> Tone:
        return dict(self.tones).get("" if value is None else str(value), "neutral")


_FORMATTER = string.Formatter()


class _RowFields(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return ""


def card_text(template: str, record: Mapping[str, Cell]) -> str:
    """``template`` filled from ``record`` (a row as a dict); "" when every
    field it names is blank, so a card leaves out a detail it has no value for."""
    fields = _RowFields({k: "" if _blank(v) else str(v) for k, v in record.items()})
    names = [name for _lit, name, _spec, _conv in _FORMATTER.parse(template) if name]
    if names and all(not fields[n] for n in names):
        return ""
    return _FORMATTER.vformat(template, (), fields)


@dataclass(frozen=True)
class Stat:
    """One headline number: a label, the value as the teacher should read it
    (already formatted, e.g. ``"75%"``), an optional detail line, and
    ``action`` for the one tile that asks the teacher to act (it takes the
    accent colour, which is otherwise kept for where you are and what you
    can press)."""

    label: str
    value: str
    detail: str = ""
    action: bool = False


STAT_COLUMNS = ["Label", "Value", "Detail", "Action"]


def stat_table(stats: Iterable[Stat]) -> Table:
    """The table a :class:`StatTiles` output fills from."""
    return Table(list(STAT_COLUMNS), [[s.label, s.value, s.detail, s.action] for s in stats])


def stats_from_table(table: Table) -> list[Stat]:
    """Read back what :func:`stat_table` wrote (missing columns default)."""
    out: list[Stat] = []
    for record in table.to_dicts():
        out.append(
            Stat(
                label=str(record.get("Label") or ""),
                value=str(record.get("Value") if record.get("Value") is not None else ""),
                detail=str(record.get("Detail") or ""),
                action=bool(record.get("Action")),
            )
        )
    return out


@dataclass(frozen=True)
class StatTiles:
    """A row of headline numbers (``tables[key]``, built with :func:`stat_table`):
    the first thing a teacher reads after a run. Sits over the main view."""

    key: str
    label: str = "Headline"
    place: Place | None = None  # None: top


@dataclass(frozen=True)
class BarChart:
    """A bar chart the shell draws in the theme's colours from ``tables[key]``:
    one bar per row, ``category`` under it, ``value`` as its height and the
    number over it, and ``detail`` (formatted with ``detail_format``, e.g.
    ``"{:g}%"``) under the category. Rows whose category is in ``skip`` are
    listed in the chart's table view but not drawn. A *Table* switch shows the
    rows themselves. ``texts[key]``, if set, is a short caption in the heading.

    The shell's chart is for the screen; a tool that saves a chart as a file
    still draws that file itself (and lists it in ``RunResult.files``)."""

    key: str
    label: str = "Chart"
    category: str = "Category"
    value: str = "Count"
    detail: str | None = None
    detail_format: str = "{:g}"
    skip: tuple[str, ...] = ()
    place: Place | None = None


@dataclass(frozen=True)
class ImageView:
    """Shows a PNG produced by the run (``RunResult.images[key]``)."""

    key: str
    label: str = "Chart"
    place: Place | None = None


@dataclass(frozen=True)
class TextView:
    """A read-only block of text (``RunResult.texts[key]``), e.g. a diff.
    ``copy_button`` adds a Copy button that puts the text on the clipboard.
    ``code`` shows it as the code views do: numbered lines, highlighted.

    ``optional`` (for a main view) shows its tab only while the latest run
    filled it: for text one kind of run makes and another does not (a quiz's
    Kahoot rows, which a printable do-now has no use for)."""

    key: str
    label: str = "Output"
    monospace: bool = True
    copy_button: bool = False
    place: Place | None = None
    code: bool = False
    optional: bool = False


@dataclass(frozen=True)
class Pages:
    """What a :class:`PagePreview` shows after a run: the PDFs it wrote.

    ``sheet`` and ``key`` are the sheet's and the answer key's PDF (``key`` is
    None for a document without answers). With no PDF at all (the teacher
    asked for Word only) the preview shows ``note`` instead of pages, over
    ``sheet_text`` / ``key_text`` (the plain-text rendering, so the tab is
    never empty). Build it with :func:`pages_from`."""

    sheet: Path | None = None
    key: Path | None = None
    note: str = ""
    sheet_text: str = ""
    key_text: str = ""

    @property
    def has_pdf(self) -> bool:
        return self.sheet is not None or self.key is not None


NO_PDF_NOTE = (
    "No PDF this time: Output is set to docx only, so there are no pages to show. "
    "Choose pdf or both to see the printed pages here. Below is the plain text."
)
KEY_STEM_SUFFIX = "_key"


def pages_from(
    files: Iterable[Path],
    *,
    sheet_text: str = "",
    key_text: str = "",
    note: str = NO_PDF_NOTE,
) -> Pages:
    """The :class:`Pages` for the files a run wrote: the sheet's PDF and its
    key's (``stem.pdf`` / ``stem_key.pdf``, as :func:`staffroom.core.export.export`
    names them). Pure: it only looks at the names. ``sheet_text`` and
    ``key_text`` are shown, under ``note``, only when no PDF was written."""
    pdfs = [f for f in files if f.suffix.lower() == ".pdf"]
    stems = {f.stem for f in pdfs}
    key = next(
        (
            f
            for f in pdfs
            if f.stem.endswith(KEY_STEM_SUFFIX) and f.stem[: -len(KEY_STEM_SUFFIX)] in stems
        ),
        None,
    )
    sheet = next((f for f in pdfs if f != key), None)
    if sheet is None and key is None:
        return Pages(note=note, sheet_text=sheet_text, key_text=key_text)
    return Pages(sheet=sheet, key=key)


@dataclass(frozen=True)
class PagePreview:
    """The pages a run wrote, as they will print (``RunResult.pages[key]``, a
    :class:`Pages`): the current page large, thumbnails of every page of the
    sheet and the key beside it, *Open PDF* and *Print…*. It takes two main
    tabs, ``sheet_label`` and ``key_label`` (the Key tab only when there is a
    key). A run whose result has no ``pages[key]`` hides both tabs (e.g. a
    quiz exported for Kahoot has nothing to print)."""

    key: str
    label: str = "Pages"
    sheet_label: str = "Sheet"
    key_label: str = "Key"
    place: Place | None = None


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
    place: Place | None = None  # None: below the main view


@dataclass(frozen=True)
class LogArea:
    """The run log. Always behind the output pane's *Details* toggle; kept in
    the vocabulary so panels that list it stay valid."""

    key: str = "log"
    label: str = "Log"


OutputWidget = (
    ResultsTable
    | CardList
    | ActionTable
    | ImageView
    | TextView
    | StatTiles
    | BarChart
    | PagePreview
    | LogArea
)
ViewWidget = (
    ResultsTable
    | CardList
    | ActionTable
    | ImageView
    | TextView
    | StatTiles
    | BarChart
    | PagePreview
)
MainLayout = Literal["tabs", "row"]


def _placed(widget: ViewWidget) -> Place:
    if widget.place is not None:
        return widget.place
    if isinstance(widget, StatTiles):
        return "top"
    return "below" if isinstance(widget, ActionTable) else "main"


def _views(outputs: tuple[OutputWidget, ...]) -> list[ViewWidget]:
    return [w for w in outputs if not isinstance(w, LogArea)]


def top_outputs(outputs: tuple[OutputWidget, ...]) -> list[ViewWidget]:
    """The headline views over the main view, in spec order."""
    return [w for w in _views(outputs) if _placed(w) == "top"]


def main_outputs(outputs: tuple[OutputWidget, ...]) -> list[ViewWidget]:
    """The output pane's main views, in spec order (tabs when more than one,
    unless the panel lays them out in a row).

    A panel whose outputs are all ``"below"`` gets its first one promoted, so
    the pane never opens on nothing but secondary lists."""
    views = [w for w in _views(outputs) if _placed(w) != "top"]
    main = [w for w in views if _placed(w) == "main"]
    return main or views[:1]


def below_outputs(outputs: tuple[OutputWidget, ...]) -> list[ViewWidget]:
    """The secondary views stacked under the main view, in spec order."""
    main = main_outputs(outputs)
    return [w for w in _views(outputs) if w not in main and _placed(w) != "top"]


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
    The shell shows ``"<verb> <folder>"`` under the Run button and, until the
    first run, a chip labelled ``open_label`` in the result strip that opens
    the folder (creating it if need be)."""

    folder: Callable[[Mapping[str, Any], Config], Path]
    verb: str = DEFAULT_WRITES_VERB
    open_label: str = DEFAULT_OPEN_LABEL


# ---------------------------------------------------------------- what a tool found
@dataclass(frozen=True)
class Found:
    """What a tool found in one input, for the shell to show beside it (see
    ``PanelSpec.inspect``): ``notes`` under it (a tick for each ``ok`` line,
    a warning mark for the others), ``rows`` that its *Preview* link
    (``rows_label``) opens in a window, and, for a :class:`ChipChoice`, its
    ``chips`` (None leaves the chips as they are)."""

    notes: tuple[Note, ...] = ()
    rows: Table | None = None
    rows_label: str = "Preview rows"
    chips: tuple[ChipOption, ...] | None = None


@dataclass(frozen=True)
class Inspection:
    """What ``PanelSpec.inspect`` returns: a :class:`Found` per input key,
    the run button's text for these inputs ("" keeps ``run_label``), and a
    new placeholder per :class:`TextArea` or :class:`TextField` key (a key
    left out keeps the spec's own), e.g. an Inputs box that says how many
    ``input()`` calls the program has (#21)."""

    found: Mapping[str, Found] = field(default_factory=dict)
    run_label: str = ""
    placeholders: Mapping[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------- the panel
@dataclass(frozen=True)
class PanelSpec:
    """A tool's whole UI as data (see the module doc).

    ``shown_when`` hides a whole input group while it does not apply, as
    ``OptionsForm.shown_when`` hides a field: ``{"taught_log":
    shown_when("options.retrieval", True)}`` shows quiz's taught-log picker
    only while the options form's *Retrieval mode* is ticked. ``on`` reads a
    field of one of the panel's options forms (``"<form key>.<field>"``) or a
    :class:`Choice` (its key, inner choices included). An input whose
    condition reads something hidden (a form field its form hides, or an input
    hidden in turn) is hidden too.

    A hidden input keeps what the teacher put in it, so it comes back
    unchanged, but the tool is handed its empty value (:func:`empty_values`,
    :meth:`passed`), and a required one is not asked for: what the teacher
    cannot see never reaches, or blocks, a run. Unknown keys, a value the
    field can never hold and loops are refused when the spec is built.

    ``joined`` names inputs that continue the group above them: no hairline
    between, and their label drawn small, as part of the same step (quiz's
    topic chips and taught log under *Questions from*).

    ``inspect`` reads what the inputs hold and says what it found: the
    inputs dict (as handed to the tool) -> an :class:`Inspection`. The shell
    calls it when the panel opens and whenever an input changes, and shows
    each :class:`Found` beside its input: notes under a file (*13 questions ·
    6 topics · no problems*, or the first problem with its line), the rows a
    *Preview* link opens, the chips of a :class:`ChipChoice` (a bank's own
    topics) and a running total under them; it may also name the run button
    (*Make do-now*). It is the plugin's code, not ``logic``: it may read the
    files the inputs name (tables through :func:`staffroom.core.csvio.read_table`
    like every other table), must be quick, and is only a hint: an exception
    is logged and the panel carries on."""

    title: str
    description: str = ""
    inputs: tuple[InputWidget, ...] = ()
    outputs: tuple[OutputWidget, ...] = field(default=(LogArea(),))
    run_label: str = "Run"
    writes_to: WritesTo | None = None  # None: the shared output folder
    main_layout: MainLayout = "tabs"  # "row": main views side by side, not tabs
    # Pure: the current inputs -> new values for Choice keys (see the module doc).
    suggest: Callable[[Mapping[str, Any]], Mapping[str, str]] | None = None
    # Input key -> the condition under which the input applies (see the class doc).
    shown_when: Mapping[str, ShownWhen] = field(default_factory=dict)
    # Inputs drawn as part of the group above them (see the class doc).
    joined: tuple[str, ...] = ()
    # The current inputs -> what the tool found in them (see the class doc).
    inspect: Callable[[Mapping[str, Any]], Inspection] | None = None

    def __post_init__(self) -> None:
        keys = [w.key for w in self.inputs] + [w.key for w in self.outputs]
        keys += self._inner_choice_keys()
        dupes = {k for k in keys if keys.count(k) > 1}
        if dupes:
            msg = f"duplicate widget keys in panel {self.title!r}: {sorted(dupes)}"
            raise ValueError(msg)
        sources = {w.key for w in self.inputs if isinstance(w, FilePicker)}
        code_sources = {w.key for w in self.inputs if isinstance(w, CodeSource)}
        for out in self.outputs:
            if (
                isinstance(out, ResultsTable | CardList)
                and out.line_column
                and (out.line_source not in code_sources)
            ):
                msg = (
                    f"{type(out).__name__} {out.key!r} points its lines at "
                    f"{out.line_source!r}, which is not a CodeSource of this panel"
                )
                raise ValueError(msg)
        seen: set[str] = set()
        for w in self.inputs:
            seen.add(w.key)
            if isinstance(w, TablePreview) and w.source not in sources:
                msg = f"TablePreview {w.key!r} refers to unknown FilePicker {w.source!r}"
                raise ValueError(msg)
            if isinstance(w, TablePreview) and w.compact and w.source not in seen:
                msg = f"compact TablePreview {w.key!r} must come after its FilePicker {w.source!r}"
                raise ValueError(msg)
            if isinstance(w, EditableTable) and w.compact and len(w.columns) != 2:
                msg = f"compact EditableTable {w.key!r} needs two columns (label, number)"
                raise ValueError(msg)
            if isinstance(w, OptionsForm) and w.fields:
                names = {f.name for f in dataclasses.fields(w.schema)}
                unknown = sorted(set(w.fields) - names)
                if unknown:
                    msg = f"OptionsForm {w.key!r} lists fields {unknown} that are not in its schema"
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
        self._check_shown_when()
        input_keys = [w.key for w in self.inputs]
        for key in self.joined:
            if key not in input_keys:
                msg = f"panel {self.title!r}: joined names {key!r}, not an input of the panel"
                raise ValueError(msg)
            if input_keys.index(key) == 0:
                msg = f"panel {self.title!r}: joined {key!r} is the first input; nothing to join"
                raise ValueError(msg)

    def _condition_source(self, on: str) -> tuple[str, OptionsForm | Choice, str] | None:
        """What a panel-level condition reads: the input that holds it (the
        form, the choice, or the input a choice sits inside), the form or
        choice itself, and the form field's name ("" for a choice)."""
        form_key, dot, name = on.partition(".")
        for w in self.inputs:
            if dot and isinstance(w, OptionsForm) and w.key == form_key:
                return w.key, w, name
            if not dot and isinstance(w, Choice) and w.key == on:
                return w.key, w, ""
            if (
                not dot
                and isinstance(w, EditableTable | CodeSource)
                and w.choice is not None
                and w.choice.key == on
            ):
                return w.key, w.choice, ""
        return None

    def _check_shown_when(self) -> None:
        by_key = {w.key: w for w in self.inputs}
        for key, cond in self.shown_when.items():
            where = f"panel {self.title!r}: shown_when[{key!r}]"
            widget = by_key.get(key)
            if widget is None:
                msg = f"{where} names no input of the panel"
                raise ValueError(msg)
            if isinstance(widget, TablePreview) and widget.compact:
                msg = f"{where}: a compact TablePreview shows and hides with its FilePicker"
                raise ValueError(msg)
            source = self._condition_source(cond.on)
            if source is None:
                msg = (
                    f"{where} reads {cond.on!r}, which is neither '<form key>.<field>' of an "
                    "OptionsForm nor the key of a Choice"
                )
                raise ValueError(msg)
            _owner, control, name = source
            allowed: tuple[Any, ...] | None
            if isinstance(control, OptionsForm):
                if not dataclasses.is_dataclass(control.schema):
                    continue  # the shell says so when it builds the form
                in_form = control.fields or tuple(
                    f.name for f in dataclasses.fields(control.schema)
                )
                if name not in in_form:
                    msg = f"{where} reads {cond.on!r}: {name!r} is not a field of its form"
                    raise ValueError(msg)
                allowed = choice_values(control.schema, name)
            else:
                allowed = tuple(v for v, _ in control.choices)
            wrong = [v for v in cond.values if allowed is not None and v not in allowed]
            if wrong:
                msg = f"{where}: {cond.on!r} can never be {wrong}"
                raise ValueError(msg)
        for key in self.shown_when:  # an input may not depend on itself, even by a loop
            seen = [key]
            while (step := self.shown_when.get(seen[-1])) is not None:
                source = self._condition_source(step.on)
                owner = source[0] if source is not None else step.on
                if owner in seen:
                    msg = f"panel {self.title!r}: shown_when loops: {[*seen, owner]}"
                    raise ValueError(msg)
                seen.append(owner)

    def hidden_inputs(self, values: Mapping[str, Any]) -> frozenset[str]:
        """The inputs that do not apply to ``values`` (the ``inputs`` dict, by
        key; a missing value counts as the input's empty one)."""

        def hidden(key: str) -> bool:
            cond = self.shown_when.get(key)
            if cond is None:
                return False
            source = self._condition_source(cond.on)
            if source is None:  # pragma: no cover - refused when the spec is built
                return False
            owner, control, name = source
            if hidden(owner):
                return True
            if isinstance(control, OptionsForm):
                options = values.get(control.key)
                if options is None:
                    options = control.schema()
                if name in control.hidden(options):
                    return True
                current = getattr(options, name)
            else:
                current = values.get(control.key, control.initial)
            return current not in cond.values

        return frozenset(key for key in self.shown_when if hidden(key))

    def passed(self, values: Mapping[str, Any]) -> dict[str, Any]:
        """``values`` as handed to the tool: every hidden input at its empty
        value (:func:`empty_values`)."""
        out = dict(values)
        hidden = self.hidden_inputs(values)
        for w in self.inputs:
            if w.key in hidden:
                out.update(empty_values(w))
        return out

    def _inner_choice_keys(self) -> list[str]:
        """Keys of the choices that live inside another input's group."""
        return [
            w.choice.key
            for w in self.inputs
            if isinstance(w, EditableTable | CodeSource) and w.choice is not None
        ]

    def input_keys(self) -> list[str]:
        keys = [w.key for w in self.inputs if not isinstance(w, TablePreview)]
        keys += self._inner_choice_keys()
        return keys

    def refresh_actions(self) -> list[str]:
        return [
            w.refresh_action
            for w in self.outputs
            if isinstance(w, ActionTable) and w.refresh_action is not None
        ]


# ---------------------------------------------------------------- handing a file to a tool
@dataclass(frozen=True)
class FileInput:
    """A panel's main file input: the widget ``key`` a file is handed to and
    the ``extensions`` it accepts (lower case, with the dot; () for any file)."""

    key: str
    extensions: tuple[str, ...]

    @property
    def any_file(self) -> bool:
        return not self.extensions

    def accepts(self, path: str | Path) -> bool:
        """True when a file named ``path`` can be handed to this input. The
        last suffix counts, so ``loops.ocr.txt`` is a ``.txt``."""
        return self.any_file or Path(path).suffix.lower() in self.extensions


def main_file_input(spec: PanelSpec) -> FileInput | None:
    """The panel's main file input: its first :class:`CodeSource`,
    :class:`ResourcePicker` or :class:`FilePicker` that opens a file (a save
    picker is a destination, not an input). None when the tool takes no file.

    The shell builds the Library's use bar from this, so a tool appears there
    for the extensions its own picker declares, with no library change."""
    for widget in spec.inputs:
        if isinstance(widget, CodeSource | ResourcePicker) or (
            isinstance(widget, FilePicker) and widget.mode == "open"
        ):
            return FileInput(widget.key, widget.extensions)
    return None


def tools_accepting(inputs: Mapping[str, FileInput | None], path: str | Path) -> list[str]:
    """The tools (keys of ``inputs``, in its order) whose main file input
    takes a file named ``path``. A tool that takes *any* file is left out: it
    says nothing about what this file is for (Classroom, the one such tool,
    has its own *Open for class* on the use bar)."""
    return [
        name
        for name, file_input in inputs.items()
        if file_input is not None and not file_input.any_file and file_input.accepts(path)
    ]
