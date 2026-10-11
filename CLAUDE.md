# Staffroom — conventions

A monorepo of small Python tools for UK secondary computing teachers (KS3,
GCSE OCR J277 / AQA 8525, A-level), run locally on the teacher's own Mac. Outputs (PDF, docx,
CSV, PNG) are taken into school systems by hand. Optimise for the teacher's
workflow, not for deployment.

`docs/ROADMAP.md` and `docs/PHASES.md` are the source of truth for what gets
built and in what order. Read them before starting a phase. The rules below
are copied from them so no session can miss them.

## Hard rules

### No pupil data — ever
This project stores and processes **no personally identifiable pupil data**. Explicitly excluded, and not to be
built, imported, or accepted as input by any tool:

- Class lists, registers, names, initials, candidate numbers, UPNs, email addresses, photos.
- Seating plans or anything that maps a pupil to a position, group or partner.
- Per-pupil anything: feedback, targets, grades, behaviour, praise, SEND/PP/EAL flags, attendance.
- Any import from SIMS, Arbor, Go4Schools, Class Charts or similar.

What **is** allowed: class-level, generalised results only. `marks` accepts rows of raw marks with **no identifier
column** (or an opaque, teacher-generated row number that is discarded on save). Everything persisted is an
aggregate: distributions, facility indices, per-question stats, charts. Nothing saved can be traced to a pupil.

Enforcement: pre-commit refuses CSV/XLSX without the fake-data marker; `marks` drops any column that looks like
an identifier (name, id, upn, candidate, email) with a warning; no tool has a "names" or "class" input field.

In this codebase the enforcement point is `core/privacy.py`:
`core.csvio.read_table` runs every loaded table through
`drop_identifier_columns`, so identifier columns never reach a tool, a
preview or an output, and the dropped names are logged. No tool can opt out.
Example and fixture data must be invented, marked `# FAKE DATA`, and must
contain no names even invented ones.

### Engineering rules
- Tools never import Qt. Logic never does I/O. New UI needs go into the shared widget kit.
- The resources folder is read-only to every tool. Edits happen on session copies; tags live in a sidecar.
- This project is standalone. No integration with the author's other apps; no shared data formats.

### Other rules from PHASES.md
- Pupil code is only ever executed through `core/runner` (subprocess, timeout,
  temp cwd), never with in-process `exec`.
- Legacy Office files (.doc/.ppt/.pub/.pptx/.docx/.xlsx) are never parsed for preview or search; they are
  opened externally in their native app (`open <path>` on macOS). Full-text search covers .py/.txt/.md/.csv/.pdf only.
- Thonny is the editor on the board and on school machines (IDLE is the fallback). On the Mac, launch with
  `open -a Thonny <file>`; keep the editor command configurable.
- Each phase ends with tests green, lint clean, and a `CHANGELOG.md` entry.

## Shape

```
src/staffroom/
  cli.py            staff: typer root; mounts each tool's sub-app and shell features
  core/             shared, GUI-free: Table, csvio, privacy, config, paths, log,
                    launch (editor command), plugin (ToolPlugin protocol),
                    panel (UI vocabulary), discovery (pkgutil), scaffold (staff new),
                    library/ (Resource Library: index, search, tags, service),
                    export/ (house style: Document → docx / PDF / text),
                    runner/ (sandboxed subprocess with timeout), codeinput,
                    spec/ (OCR J277 / AQA 8525 taxonomies as TOML)
  shell/            staffroom: the PySide6 launcher and its widget kit
  tools/<name>/     one package per tool: __init__ (plugin), cli, logic, panel, tests/
examples/           small FAKE data files (marker row required, no names)
data/               git-ignored scratch space
docs/               ROADMAP.md, PHASES.md, adding-a-tool.md, screenshots
```

Two entry points over the same code: `staff` (CLI, primary for testing) and
`staffroom` (launcher).
`just` has the day-to-day commands.

## The three engineering rules, as enforced here

1. **Tools never touch Qt.** Nothing under `tools/` imports PySide6, shiboken6
   or `staffroom.shell`. Enforced by an import-linter contract
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
  (FilePicker/ResourcePicker → `Path | None`, TextField → `str`,
  OptionsForm → dataclass instance, EditableTable → `Table`).
* A panel with `ActionTable` widgets needs the plugin to also implement
  `act(name, row, ctx) -> RunResult` (`SupportsActions`). The table's
  `refresh_action` is called with an empty row when the panel is shown and
  after every run or action.
* `ctx` (`RunContext`) carries `config`, `output_dir`, `progress(fraction, msg)`
  and `log(msg)`. Use them; never print from a tool.
* Raise `ToolError("message for the teacher")` for user-facing failures. Any
  other exception is treated as a bug and shown with a traceback.
* `RunResult.tables` / `.images` / `.texts` are keyed by output widget keys;
  `.files` lists what was written; `.summary` is one line.

Discovery is `pkgutil` over `staffroom.tools`: a new folder appears in
`staff list` with no reinstall. Broken tools are logged and skipped.

## Process

Branches, the Issues board, and the three skills (`/audit`, `/next-task`,
`/merge-prs`) are described in `.claude/process.md`. Task sessions work in a
git worktree on a feature branch from `dev`; `main` is what the installed
app runs. Nothing merges without a PR and green CI.

## Working here

* `just setup`, `just test`, `just lint`, `just gui`, `just new <name>`,
  `just install` (thin launcher app in /Applications), `just bundle`
  (PyInstaller), `just icon`, `just screenshots`, `just update`.
* The installed app runs this checkout via uv: commit and push to
  github.com/ColePoppleton/Staffroom and the app offers the update.
* `uv` manages the environment; Python 3.12+; src layout.
* ruff (line length 100), pytest (+ pytest-qt, offscreen), mypy (strict on
  `core`, normal elsewhere), import-linter, pre-commit.
* Tests for a tool live in `tools/<name>/tests/`; shared fixtures in the root
  `conftest.py` (every test gets an isolated `STAFFROOM_HOME`).
* The shell's look is defined in `shell/theme.py` as tokens + generated QSS.
  Widgets opt in with object names and `role` properties; no colours in
  widget code.
* Keep tools small. `hello` is the reference: read it before writing a tool.
  `marks` shows presets, charts and aggregate-only saving; `classroom`
  shows row actions and the Resource Library; `worksheet` and `parsons`
  show the house-style export; `trace`, `bugs` and `fade` show the sandboxed runner; `pseudocode` is an AST → IR → text translator.
* Screenshots for docs: `just screenshots` (renders offscreen via `staffroom
  --screenshot`).
* Config lives at `~/.config/staffroom/` (config.toml, logs/, library.db,
  usage.toml). Worksheets read the house-style header/footer from config.
  `usage.toml` holds run counts and last-used dates only; the launcher's
  worker and the `staff` command wrapper (`cli._guard_tool_command`) both
  record into it, so tools never call `record_run` themselves.
* Lesson copies live in `~/TeachingSessions` by default (`sessions_root`).
  Never default to, or detect, any cloud-synced folder; the teacher chooses.
