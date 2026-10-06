# Teaching Tools — conventions

A monorepo of small Python tools for a UK secondary computing teacher (KS3,
GCSE OCR/AQA, A-level), run locally on a Mac. Outputs (CSV/XLSX/PDF/DOCX/PNG)
are carried into school systems by hand. Optimise for the teacher's workflow,
not for deployment.

## Shape

```
src/teaching_tools/
  cli.py            tt: typer root; mounts each tool's sub-app
  core/             shared, GUI-free: Table, csvio, config, paths, log,
                    plugin (ToolPlugin protocol), panel (UI vocabulary),
                    discovery (pkgutil), scaffold (tt new)
  shell/            tt-gui: the PySide6 launcher and its widget kit
  tools/<name>/     one package per tool: __init__ (plugin), cli, logic, panel, tests/
examples/           small FAKE data files (marker row required)
data/               git-ignored scratch space for real files
docs/adding-a-tool.md
```

Two entry points over the same code: `tt` (CLI, primary for testing) and
`tt-gui` (launcher). `just` has the day-to-day commands.

## The three rules

1. **Tools never touch Qt.** Nothing under `tools/` imports PySide6, shiboken6
   or `teaching_tools.shell`. Enforced by an import-linter contract
   (`just lint`) and by `tests/test_boundaries.py` (`just test`).
2. **Logic never touches I/O.** `tools/<name>/logic.py` is pure functions over
   `core.table.Table` and plain values: no files, no typer, no Qt, no network.
   File reading/writing happens in the plugin's `run()` or `cli.py` using
   `core.csvio`. The boundary test scans `logic.py` for I/O modules.
3. **New UI needs go into the shared widget kit, not into a tool.** A tool
   describes its UI with the dataclasses in `core/panel.py`. If a tool needs a
   widget that does not exist, add the spec to `core/panel.py`, the widget to
   `shell/widgets/`, and the rendering case to `shell/tool_panel.py`. Then
   every tool can use it.

## Plugin contract (`core/plugin.py`)

A tool package exposes `plugin`, an object with `name`, `description`,
`version`, `register_cli(app)`, `panel_spec() -> PanelSpec`, and
`run(inputs, ctx) -> RunResult`. `name` must equal the package name.

* `inputs` is a dict keyed by the panel's input widget keys
  (FilePicker → `Path | None`, OptionsForm → dataclass instance,
  EditableTable → `Table`).
* `ctx` (`RunContext`) carries `config`, `output_dir`, `progress(fraction, msg)`
  and `log(msg)`. Use them; never print from a tool.
* Raise `ToolError("message for the teacher")` for user-facing failures. Any
  other exception is treated as a bug and shown with a traceback.
* `RunResult.tables` / `.images` are keyed by output widget keys;
  `.files` lists what was written; `.summary` is one line.

Discovery is `pkgutil` over `teaching_tools.tools`: a new folder appears in
`tt list` with no reinstall. Broken tools are logged and skipped.

## Data safety

Never commit real pupil data. Example files carry a marker (`# FAKE DATA` as
the first CSV line; a `FAKE DATA` cell in the first rows of an XLSX). The
pre-commit hook refuses CSV/XLSX files without it. `core.csvio.read_table`
strips the marker and sets `Table.fake_data`; `write_table` puts it back.

## Working here

* `just setup`, `just test`, `just lint`, `just gui`, `just new <name>`.
* `uv` manages the environment; Python 3.12+; src layout.
* ruff (line length 100), pytest (+ pytest-qt, offscreen), mypy (strict on
  `core`, normal elsewhere), import-linter, pre-commit.
* Tests for a tool live in `tools/<name>/tests/`; shared fixtures in the root
  `conftest.py` (every test gets an isolated `TEACHING_TOOLS_HOME`).
* The shell's look is defined in `shell/theme.py` as tokens + generated QSS.
  Widgets opt in with object names and `role` properties; no colours in
  widget code.
* Keep tools small. `hello` is the reference: read it before writing a tool.
* Screenshots for docs: `just screenshots` (renders offscreen via `tt-gui
  --screenshot`).
