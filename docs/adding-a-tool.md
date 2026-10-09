# Adding a tool

## 1. Scaffold

```bash
just new my_tool
```

This creates `src/staffroom/tools/my_tool/` with:

| File | Owns |
| --- | --- |
| `__init__.py` | the `plugin` object: metadata, `run()` glue (reads/writes files, calls logic) |
| `logic.py` | pure functions and an `Options` dataclass; no I/O |
| `panel.py` | `panel_spec()`: the declarative UI |
| `cli.py` | `staff my_tool run ...` and friends |
| `tests/` | tests; shared fixtures come from the root `conftest.py` |

It shows up straight away:

```bash
uv run staff list
uv run staff my_tool run examples/marks_10x.csv
```

`hello` is the reference tool: read `src/staffroom/tools/hello/` before
writing your own. It is `hidden`, so it is not in the launcher sidebar, but
`staff hello run` works and its tests run with everything else.

## Where it sits in the sidebar

The sidebar groups tools by the shape of a teacher's week (`GROUPS` in
`core/plugin.py`), and the `⌘1`–`⌘9` shortcuts follow it top to bottom:

| Group | Shipped tools | Shortcuts |
| --- | --- | --- |
| Lessons | (Library), classroom | ⌘K, ⌘1 |
| Sheets & quizzes | worksheet, quiz | ⌘2, ⌘3 |
| From a program | parsons, trace, bugs, fade, pseudocode | ⌘4 – ⌘8 |
| After a test | marks | ⌘9 |

The Library is the shell's own page, not a tool, so it has ⌘K rather than a
number. Four optional class attributes on the plugin say where a tool goes and
how it looks; all are read with `getattr`, so a tool that sets none needs no
change: it is listed under **Other**, after every group, A-Z, with a generic
glyph.

```python
class MyToolPlugin:
    name = "my_tool"
    ...
    group = "From a program"  # one of core.plugin.GROUPS, or a name of your own
    glyph = "code"  # a file in shell/assets/glyphs/ (without .svg)
    order = 35  # within the group: lower first; shipped tools use 10 × their WORKFLOW_ORDER place
    hidden = True  # not in the sidebar or on a shortcut; still a CLI tool
```

`group` names one of the four groups; a name of your own makes a new group
after them. `glyph` picks one of the bundled monochrome glyphs (`books`,
`screen`, `page`, `question`, `blocks`, `table`, `bug`, `taper`, `code`,
`chart`, `tool`); the shell paints it in the theme's colours, so the tool
stays Qt-free. To add a glyph, drop a 24×24 line drawing that uses
`currentColor` for its stroke into `shell/assets/glyphs/`. `order` places the
tool among the shipped ones in its group (35 puts it between parsons and
trace in *From a program*). `hidden` is for reference and developer tools:
`staff list` still shows them, marked `[hidden]`, and `staffroom --tool <name>`
still opens them for a screenshot.

## 2. Write the logic

Put the real work in `logic.py` as functions over `Table` (see
`core/table.py`). Keep them pure so tests are one-liners:

```python
def process(table: Table, options: Options) -> Table:
    return table.with_column("Total", lambda row: sum(...))
```

Add fields to `Options` and the form draws itself. Field `metadata` can set
`label`, `help`, `min`, `max`, `step`. Supported types: `bool`, `int`,
`float`, `str`, `Literal[...]`, `Enum`.

## 3. Declare the panel

`panel.py` returns a `PanelSpec` built only from `core/panel.py`:

```python
PanelSpec(
    title="Marks",
    inputs=(
        FilePicker(key="marks", label="Marks file"),
        TablePreview(key="preview", source="marks"),
        EditableTable(
            key="boundaries",
            label="Grade boundaries",
            columns=(Column("Grade"), Column("Min mark", "int")),
            rows=(("9", 36), ("7", 28), ("4", 16), ("1", 0)),
        ),
        OptionsForm(key="options", schema=Options),
    ),
    outputs=(
        ResultsTable(key="grades", label="Grades"),
        ResultsTable(key="questions", label="Per-question analysis"),
        ImageView(key="distribution", label="Cohort distribution"),
        LogArea(),
    ),
    run_label="Analyse",
)
```

Input keys become the keys of the `inputs` dict passed to `run()`; output keys
are what `run()` must put in `RunResult.tables` / `RunResult.images`.

The shell lays every panel out as a workbench: the inputs in a column on the
left with the run button at its foot (⌘↵ runs it), the outputs on the right.
Outputs are *main* views, shown as tabs in spec order, or sit *below* them.
An `ActionTable` goes below by default and everything else is a main view; set
`place="below"` on a secondary output (notes, a view-only table) or
`place="main"` on a list that is the point of the tool, as classroom's
sessions are. The `LogArea` stays at the foot of the output pane.

For a tool whose result is a report rather than one view, `tools/marks` is
the reference:

- `StatTiles(key)` is a row of headline numbers over the main view
  (`place="top"` by default). Fill it with
  `tables[key] = stat_table([Stat("Mean", "75%", "29.9 / 40"), ...])`;
  `Stat(..., action=True)` marks the one that asks the teacher to act (the only
  result that takes the accent colour).
- `PanelSpec(main_layout="row")` puts the main views side by side, each in a
  titled card, instead of tabs; they stack when the pane is too narrow.
- `BarChart(key, category=..., value=..., detail=..., detail_format="{:.0f}%")`
  draws bars from `tables[key]` in the theme's colours with a *Table* switch;
  `texts[key]` is its caption. A file for reports still comes from the tool.
- `ResultsTable(..., bars=(BarColumn("Facility", 1.0),), tag_column="Reteach",
  hidden_columns=("Note",))` draws an inline bar beside a 0–1 number, tags a
  row under its first cell (the column itself is not shown), and moves
  columns into the row's tooltip. `collapsed=True` on a `place="below"` table
  folds it under its label until opened.

On the input side, `FilePicker(..., chip=True)` shows the chosen file as a
chip; `TablePreview(..., summary=fn, flag="MAX", compact=True)` replaces the
rows with a few `Note` lines from `fn(table)` and a *Preview rows* link;
`EditableTable(..., compact=True, choice=Choice(...))` draws a two-column
table as a grid of label and number cells with a segmented switch above it
(its value reaches `run()` under the choice's key); `Choice` also works on
its own; and `OptionsForm(..., fields=(...))` shows only the named fields.

## 4. Wire `run()`

```python
def run(self, inputs, ctx):
    source = inputs["marks"]
    if source is None:
        raise ToolError("Choose a marks file first.")
    table = read_table(source)
    ctx.progress(0.3, "Grading")
    graded = logic.grade(table, inputs["boundaries"], inputs["options"])
    out = write_table(graded, ctx.output_dir / f"{source.stem}_graded.csv")
    chart = ctx.output_dir / f"{source.stem}_distribution.png"
    ...  # draw and save the PNG
    return RunResult(
        tables={"grades": graded},
        images={"distribution": chart},
        files=[out, chart],
        summary=f"Graded {len(graded)} pupils",
    )
```

`ctx.output_dir` is the configured output folder, the input's folder, or
`<sessions root>/outputs/<tool>/` when there is no input; never the current
directory. In a CLI resolve it with `config.output_dir_for(source, "<tool>")`.
`ctx.resources` is the Resource Library (`None` under a bare CLI run): use
`ctx.resources.search("while")` or `ctx.resources.pick(".py")` to let the
teacher choose a file from the indexed resources instead of a raw file
dialog, and `ctx.resources.open_externally(path)` to hand a file to its
native app. Never read Office files yourself.

## 5. CLI

Keep `cli.py` thin: parse arguments, build an `Options`, call `plugin.run`,
echo `result.summary`. The GUI and CLI must do the same thing.

## 6. Test, lint, commit

```bash
just test
just lint
```

The boundary tests fail if the tool imports Qt or if `logic.py` does I/O.
The pre-commit hook refuses any CSV/XLSX without a `# FAKE DATA` first line.

## Running pupil code

Never `exec` it in the app. Use `core.runner.run_source(source, stdin=...,
timeout=...)` (or `run_file`), which runs it in a subprocess with a hard
timeout, a temp working directory and a 1 MB cap on each of stdout and
stderr (`MAX_OUTPUT_BYTES`; the rest is drained and discarded, the text ends
with `truncation_marker()` and the outcome's `stdout_truncated` /
`stderr_truncated` say so). It returns stdout, stderr, exit code and whether
it timed out. `tools/trace` shows how to ship a helper script alongside the
program with `extra_files`. Put `core.runner.limits_note(timeout)` in the
panel description so the teacher sees the limits, and keep
`docs/guide/running-code.md` true: it is a fence against accidents, not a
sandbox.

## Producing worksheets and keys

Build a `core.export.Document`, add blocks to `doc.section()` and to
`doc.section("Answer key", answers=True)`, then call
`export(doc, ctx.output_dir, stem, formats)`. That writes the sheet and a
separate key in each format with the house header and footer. `to_text(doc)`
gives a preview for a `TextView`. `tools/worksheet` and `tools/parsons` are
the references. The blocks are `Heading`, `Paragraph`, `Code`, `Numbered`,
`TableBlock`, `HintBox`, `BoxedBlocks` (numbered cut-out cells with dashed
cut lines, laid out in columns), `AnswerGrid` (empty boxes headed by
position) and `PageBreak`. A new block goes in `core/export/model.py` with a
rendering in each of `pdf.py`, `docx.py` and `text.py`, so every tool gets it.

## Presets for an options form

`OptionsForm(..., presets=(preset("Year 9", top_level_only=True), ...))` puts
a Preset dropdown above the fields. A preset pins some fields of the schema
(`core.panel.preset(name, **values)`); choosing it sets those and leaves the
rest as the teacher had them, and editing a field afterwards moves the
dropdown to whichever preset still matches, or to *Custom*. The same rule is
`core.panel.matching_preset(presets, options)`: call it in `logic` to print
the preset's name on the output, so a sheet says which preset it came from
even when the options were typed on the command line (`trace` does this).
Keep the presets in `logic.py` next to the options dataclass; the panel just
passes them on.

## Presets for an editable table

`EditableTable(..., presets=(("OCR J277", rows), ...), preset_action="save_preset")`
shows a preset dropdown with Apply and Save as preset (with `compact=True`,
choosing a preset applies it and *Save as preset* sits in the group heading). Saving calls
`plugin.act("save_preset", {"name": str, "table": Table}, ctx)`; persist it
in `ctx.config.tool("<tool>")` and build the `presets` tuple from config in
`panel_spec()` so it is there next launch. `tools/marks` is the reference.

## Row actions (tables with buttons)

Declare an `ActionTable(key, label, actions=(Action("diff", "Diff"), ...),
refresh_action="refresh")` among the outputs and give the plugin an
`act(name, row, ctx) -> RunResult` method. The shell calls
`act("refresh", {}, ctx)` when the panel is shown and after every run or
action, and `act("diff", row, ctx)` when a row is selected and the button
pressed. Put the result in `RunResult.texts` for a `TextView`, or return the
refreshed table under the same key. `tools/classroom` is the reference.

## If the widget you need does not exist

Do not build it in the tool. Add a dataclass to `core/panel.py`, a widget to
`shell/widgets/`, a rendering branch in `shell/tool_panel.py` (inputs) or
`shell/widgets/output_pane.py` (outputs), and a test. Then use it from the spec.
