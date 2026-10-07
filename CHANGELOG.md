# Changelog

## Phase 3 — house style, parsons, worksheet (2026-10-07)

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

## Phase 2 — marks (2026-10-06)

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

## Phase 1b — classroom (2026-10-06)

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

## Phase 1a — Resource Library (2026-10-06)

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

## Phase 0 — Skeleton (2026-10-06)

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
