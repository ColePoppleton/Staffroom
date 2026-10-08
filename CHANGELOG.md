# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). Add a line under **Unreleased**
with every change; `just release <part>` turns it into a version.

## [Unreleased]

### Added
- Thin launcher app (`just install`) and self-update from the git remote.
- Semantic versioning, Keep-a-Changelog, tag-driven GitHub Releases with a
  wheel and sdist (`.github/workflows/release.yml`, `scripts/release.py`,
  `just release`). `uv tool install` is the canonical install.
- MIT licence.
- Branch model, Issues board, the `/audit`, `/next-task` and `/merge-prs`
  skills, and CI.

## [0.1.0] - 2026-10-08

The seven roadmap phases, as built:

### Phase 7 — polish and packaging (2026-10-08)

- Installed as a thin launcher: `just install` builds `Teaching Tools.app`
  whose executable runs the checkout with uv, and copies it into
  /Applications. Nothing to rebuild on a code change.
- Self-update: `tt update` (and `--check`), an Updates card in Settings
  (check / update now), a startup check with an "Update available" notice
  in the sidebar. Fast-forward only; a dirty tree or diverged branch is
  reported, never overwritten. Tested against a local bare remote.
- The PyInstaller bundle is still available as `just bundle` for a machine
  without the repo.
- Code now lives at github.com/ColePoppleton/Teaching-Tools (private).
- App icon (drawn by `scripts/make_icon.py`, `just icon`): icon.png for the
  window and Dock, icon.icns for the bundle.
- Theme check: every panel rendered in dark and light offscreen; no fixes
  were needed beyond what earlier phases already settled.
- Shortcuts: ⌘K jumps to the Resources search box, ⌘O opens the classroom
  tool with the library picker, ⌘1–⌘9 switch tools, ⌘L toggles the log,
  ⌘, opens Settings. Sidebar tooltips show them.
- Settings now covers the resources folder, the sessions folder, the editor
  command, the exam board (sets the default marks preset and tags) and the
  house-style header and footer text printed on every worksheet and key.
- `just app` builds `dist/Teaching Tools.app` with PyInstaller from
  `packaging/tt-gui.spec` (tools, assets, spec files and the tracer are
  collected explicitly because discovery is dynamic).
- `tt usage`: run counts and last-used dates per tool, recorded by the
  launcher and nothing else, so the "which tools were actually used in a
  month" review in PHASES.md can be done from evidence. The review itself
  is a decision for after a month of use.

### Phase 6 — quiz (2026-10-08)

- `core/spec/`: OCR J277 and AQA 8525 content maps as TOML data files with a
  loader (`load_taxonomy`, `find`, `describe`). Indicative: check against
  the current specification.
- `tools/quiz`: Markdown question banks (`## ` per question; `type: mcq |
  short | tf`; `tags:` with spec codes and `topic:` tags; `- [x]` options;
  `answer:`; `time:`; `why:`), validated with line-numbered errors.
- Exporters: Kahoot (.xlsx in the template layout, headers on row 8 and
  data from row 9, plus a .csv with the same headers; 120/75-character
  limits enforced, times snapped to Kahoot's allowed values, true/false as
  two options, short answers given three borrowed distractors or skipped
  with a note), Forms paste text with a separate answers block, and a
  printable do-now through the house style with the key split off.
- Retrieval scheduler: a `date,topic` taught log (never a class or a pupil)
  picks questions from topics taught 1, 3 and 6 weeks ago (± 3 days),
  round-robin across the three windows.
- CLI: `tt quiz export --bank B --format F --topics T --spec S --n N`,
  `tt quiz retrieval --bank B --log L --date D`, `tt quiz list`,
  `tt quiz check`, `tt quiz spec ocr|aqa`.
- Examples: `question_bank.md` (13 invented questions) and `taught_log.csv`.
- Manual check still owed, as PHASES.md says: import `question_bank_kahoot.xlsx`
  into Kahoot once and confirm it accepts the columns.
- Banks are Markdown (and could be TOML) rather than YAML, to avoid a
  dependency.

### Phase 5 — pseudocode (2026-10-07)

- `tools/pseudocode`: Python ↔ OCR Exam Reference Language ↔ AQA pseudocode
  for the GCSE subset, through one intermediate representation. Covers
  variables, arithmetic (`DIV`, `MOD`, `^`), comparisons, `AND/OR/NOT`,
  if/elif/else, count loops, for-each, while, do…until / REPEAT…UNTIL,
  functions and procedures, lists and indexing, string length / substring /
  upper / lower, casts, random, basic file methods and comments.
- Anything outside the subset is kept as a comment in the output and listed
  under "Could not translate"; translations with a caveat (for-each in ERL,
  `.append` on fixed arrays, AQA `USERINPUT` losing the prompt) are listed
  as notes. Nothing is dropped silently.
- Both pseudocode dialects parse back to Python, so Python → ERL → Python
  round trips. Every OCR Booklet program 1a-8c round-trips to an
  ast-equivalent program (tested against the real files when present and
  against embedded copies always).
- Panel: file or pasted code, direction dropdown, translation pane with a
  Copy button, report pane. CLI `tt pseudocode to-ocr | to-aqa | to-python
  <file> [--from] [--save] [--out]`.
- Widget kit: `TextView(copy_button=True)` adds a Copy button to any text
  output.

### Phase 4 — sandboxed runner, trace, bugs, fade (2026-10-07)

- `core/runner/`: runs a file with `python -I -u` in a temp working
  directory with a minimal environment, hard wall-clock timeout (the process
  is killed and reported), CPU rlimit as a second guard, captured output,
  optional stdin, and an AST refusal of networking and subprocess imports.
  Not a security boundary, by design: these are the teacher's own files.
- `tools/trace`: a tracer runs inside the sandbox under `sys.settrace`,
  recording each executed line of the program with the variable values after
  it and anything printed, capped at N steps. Filter which lines are
  recorded (assignments, loop headers, ifs, calls) and which variables are
  columns. Sheet: numbered listing plus blank table; key: completed table and
  the program output. Functions get a Scope column.
- `tools/bugs`: seven error classes (comparison flipped, off by one, missing
  colon, missing bracket, wrong variable name, indentation slip, string /
  integer confusion). N variant files with exactly one mutation each; every
  variant is run in the sandbox against the original so the key says
  crashes with X, output wrong, hangs, or no visible change.
- `tools/fade`: K progressively faded versions (bottom-up, top-down or by
  line ranges; headers kept by default), one document with a page per
  version and the solution as key.
- `core/codeinput.py`: shared "file from the library or pasted code" input.
- CLI: `tt trace make`, `tt bugs make` / `tt bugs kinds`, `tt fade make`.

### Phase 3 — house style, parsons, worksheet (2026-10-07)

- `core/export/`: one document model (headings, paragraphs, code blocks,
  numbered items with answer space, tables, hint boxes, page breaks; answer
  sections) rendered to docx (python-docx), PDF (reportlab) and plain text.
  Header with title / topic / date, footer with page numbers, monospace code.
  `export()` writes `<stem>.<fmt>` and `<stem>_key.<fmt>`.
- `tools/parsons`: a .py from the library (or pasted) → blocks at statement
  level (compound headers and bodies apart) or per line, seeded shuffle,
  distractors by mutating a line (missing colon, wrong comparison, off by
  one), indentation shown or stripped, optional hint box. Key gives the
  order, the distractors and the reconstructed program. Tests prove the key
  rebuilds an ast-equal program for seven program shapes and 39 seeds.
- `tools/worksheet`: nine seeded generators (binary/denary/hex, two's
  complement, binary addition with overflow, shifts, truth tables, Boolean
  simplification with laws listed, file sizes, run-length encoding, Huffman
  weight). The seed, difficulty and count sit in the sheet header so a set
  can be regenerated. Every generator is verified by independent computation.
- CLI: `tt parsons make <file> --seed N --distractors K [--lines]
  [--no-indent] [--format]`, `tt worksheet make --topic T --count N --seed S
  [--difficulty]`, `tt worksheet topics`.
- Widget kit: `TextArea` input for pasted code.
- python-docx and reportlab added.
- Fixed: outputs for an input that lives in the resources folder were being
  written next to it. The resources folder is read-only to every tool, so
  those outputs now go to `~/TeachingSessions/outputs` unless an output
  folder is configured.

### Phase 2 — marks (2026-10-06)

- `tools/marks`: raw marks per question (q1..qn, one row per script, no
  identifiers) → per-script grades (view only), grade distribution table
  and bar chart, facility index and discrimination (top third vs bottom
  third) per question, worst-N questions to reteach.
- Max marks from a row flagged `MAX`, from the Max marks option, or (with a
  warning) the highest mark seen per question.
- Grade boundaries: editable grid as % of paper or raw marks, with built-in
  starting points for OCR J277, AQA 8525 and A-level, and "Save as preset"
  persisted to `config.tool("marks")["presets"]`.
- Saved outputs are aggregates only: `<stem>_distribution.csv`,
  `<stem>_questions.csv`, `<stem>_distribution.png`. Nothing per script is
  written; identifier columns are dropped and logged before analysis.
- CLI: `tt marks run <file> [--preset] [--unit percent|raw] [--max] [--worst]
  [--out]`, `tt marks presets`.
- Widget kit: `EditableTable` gained presets (dropdown, Apply, Save as
  preset backed by a plugin action). `ImageView` now scales to the card
  width instead of forcing the panel to the image's size.
- Colour tokens moved to `core/theme_tokens.py` so charts can use the app
  palette without a tool touching Qt. matplotlib (Agg) added.

### Phase 1b — classroom (2026-10-06)

- Library picker rebuilt as a palette after the first version proved
  unreadable: one big search field, the folder tree while it is empty, rich
  rows (name, type, folder, snippet) while typing, arrow keys and Enter to
  choose, name-substring fallback for things FTS misses. The picker field
  then shows the library-relative path rather than a long absolute one.
  Generic list, tree and dialog styling added to the theme so nothing falls
  back to Qt defaults again.
- `tools/classroom`: "Open for class" copies a resource to
  `<sessions_root>/<YYYY-MM-DD>/<label>/<file>`, records the origin in a
  `.origin.json` sidecar beside the copy, and launches the configured editor
  on the copy. Opening the same file for the same lesson re-opens the
  existing copy; edits are never overwritten. The original is only ever read.
- Session browser: past copies with Diff vs original (unified diff), Re-open,
  and Promote, which copies the edit back next to the original as
  `<name>_v2.py` (then `_v3`, never overwriting). The library picks the new
  file up on re-index.
- Sessions folder defaults to local `~/TeachingSessions`; a folder picker in
  Settings covers syncing elsewhere. No cloud-folder detection, by decision:
  the school does not use OneDrive and every OneDrive on this Mac is personal.
- Editor: `core/launch.py` turns a `{file}` command template into argv.
  Presets Thonny (`open -a Thonny {file}`, default), IDLE
  (`python3 -m idlelib {file}`), System default (`open {file}`), or Custom,
  all editable in Settings.
- CLI: `tt classroom open <resource> --label "..."`, `list`, `diff`,
  `promote`, `reopen`.
- Widget kit grew four generic pieces for this and future tools:
  `ResourcePicker` (from the library or a dialog), `TextField`,
  `ActionTable` (rows with action buttons, refreshable) and `TextView`.
  `RunResult.texts` and the optional `SupportsActions.act(name, row, ctx)`
  plugin method back them.

### Phase 1a — Resource Library (2026-10-06)

- `core/library/`: scanner with kind classification and hidden-cruft rules,
  text extraction for .py/.txt/.md/.csv/.pdf only (pypdf, 20-page cap),
  iCloud placeholders (`.name.icloud` stubs and EDEADLK reads) marked
  cloud-only instead of failing the run, SQLite + FTS5 index at
  `~/.config/teaching-tools/library.db` with incremental re-index by
  mtime/size, tags and notes in `<root>/.teaching-tools/tags.json`.
- `LibraryService` / `ResourceService`: `search`, `open_externally` (macOS
  `open`), `reveal`, `pick` (shell dialog), `open_for_class` stub for 1b.
  Plugins get it as `ctx.resources`.
- CLI: `tt library index [--full]`, `search <q> [--kind] [--tag] [--hidden]`,
  `tags <path> [--set] [--notes]`, `status`.
- Shell: sidebar Tools | Resources switch; Resources shows a search box,
  type filter, hidden toggle and a folder tree built from the index. Main
  area shows search results with snippets beside a preview pane: Python with
  syntax highlighting, plain text/markdown/CSV, images, first-page PDF text,
  and an open-externally card for Office, Scratch, media and everything
  else. Tag editor underneath. Re-index runs in a worker with progress; an
  empty index is built automatically on first launch.
- Settings: resources folder picker (changing it triggers a full re-index).
- Full index of the real root (587 files): 3.3 s; incremental: 0.0 s.
- Fixed: one SQLite commit per file made indexing take minutes; the stderr
  log handler broke under typer's CliRunner; table previews no longer
  stretch their last column.

### Phase 0 — Skeleton (2026-10-06)

- uv-managed src layout; `tt` (typer) and `tt-gui` (PySide6) entry points.
- `core/`: `Table`, CSV/XLSX I/O with fake-data marker, TOML config, paths,
  logging, `ToolPlugin` protocol, declarative panel spec, pkgutil discovery,
  `tt new` scaffolder.
- `core/privacy.py`: identifier columns (name, id, upn, candidate, email,
  class and variants) are dropped on every table load; no tool can opt out.
- `shell/`: launcher with sidebar, stacked panels, settings page, log drawer,
  dark/light theme, shared widget kit (path picker, table preview, editable
  table, options form, run bar, image view, results area).
- `tools/hello`: reference tool, reads an anonymous marks file (q1..qn) and
  adds a Total column.
- Guard rails: import-linter contracts, boundary tests, pre-commit hook
  refusing CSV/XLSX files without `# FAKE DATA`.
- Docs: CLAUDE.md with the hard rules verbatim, docs/adding-a-tool.md.
