# Adding a tool

## 1. Scaffold

```bash
just new my_tool
```

This creates `src/teaching_tools/tools/my_tool/` with:

| File | Owns |
| --- | --- |
| `__init__.py` | the `plugin` object: metadata, `run()` glue (reads/writes files, calls logic) |
| `logic.py` | pure functions and an `Options` dataclass; no I/O |
| `panel.py` | `panel_spec()`: the declarative UI |
| `cli.py` | `tt my_tool run ...` and friends |
| `tests/` | tests; shared fixtures come from the root `conftest.py` |

It shows up straight away:

```bash
uv run tt list
uv run tt my_tool run examples/marks_10x.csv
```

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

`ctx.output_dir` is the configured output folder, or the input's folder.
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

## If the widget you need does not exist

Do not build it in the tool. Add a dataclass to `core/panel.py`, a widget to
`shell/widgets/`, a rendering branch in `shell/tool_panel.py` (inputs) or
`shell/widgets/results.py` (outputs), and a test. Then use it from the spec.
