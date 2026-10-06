# Changelog

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
