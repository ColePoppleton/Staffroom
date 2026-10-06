# Changelog

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
