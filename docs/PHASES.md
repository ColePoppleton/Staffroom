# Staffroom — Build Phases

Companion to `ROADMAP.md`. Each phase is one Claude Code session or so, ends with tests green,
lint clean, and a short entry in `CHANGELOG.md`. Do not start a phase until the previous one's
acceptance criteria pass. Within a phase, work in the order listed.

Conventions that apply to every phase (also in `CLAUDE.md`):
- Tools never import Qt. `logic.py` never does I/O. New UI needs go into the shared widget kit.
- No pupil data anywhere — see `ROADMAP.md` Hard rules. No class lists, names, seating plans, per-pupil feedback or
  flags, no MIS imports. `marks` takes marks only, with no identifier column; only class-level aggregates are saved.
- This project is standalone: no integration with, or data handoff to, any other app.
- The resources root is read-only. Edits happen on session copies; tags live in a sidecar JSON.
- Legacy Office files (.doc/.ppt/.pub/.pptx/.docx/.xlsx) are **not** parsed for preview or search — they are
  opened externally in their native app (`open <path>` on macOS). Full-text search covers .py/.txt/.md/.csv/.pdf only.
- Thonny is the editor on the board and on school machines (IDLE is the fallback). On the Mac, launch with
  `open -a Thonny <file>`; keep the editor command configurable.

---

## Phase 0 — Skeleton (in progress)

Scope: uv project, `staff` CLI + `staffroom` PySide6 shell, `ToolPlugin` protocol, declarative `panel_spec()`,
shared widget kit, `staff new`, `hello` reference tool, pre-commit fake-data guard, CLAUDE.md, docs/adding-a-tool.md.

Acceptance:
- `staff list`, `staff hello run`, `staffroom` all work; hello panel renders from its spec.
- A test fails if any package under `tools/` imports PySide6.
- `staff new foo` produces a tool that passes tests without edits.
- Remove or ignore the stray `Marks Calculator - Student Complexity version` folder at the repo root.

---

## Phase 1 — Resource Library (shell feature) + `classroom`

The two things used every lesson. Build the library first; `classroom` depends on it.

### 1a. Library

Scope:
- Settings: one configurable `resources_root` (the teacher's resources folder; empty until set).
- Indexer: walk the root, record path, type, size, mtime, and extracted text for .py/.txt/.md/.csv/.pdf
  (pdf via `pypdf`; skip if text layer is empty). Store in SQLite at `~/.config/staffroom/library.db`.
  Incremental re-index by mtime; manual "Re-index" button; `staff library index` CLI.
- Cloud placeholders: a read that raises `OSError`/"Resource deadlock avoided" marks the file `cloud_only`
  and moves on. Never crash the index on one file.
- Hide by default: `.DS_Store`, `Thumbs.db`, `.zip`, `__pycache__`, `.idea`. Toggle to show.
- Sidebar gains a second root: **Resources**. Tree view of the folder, with search box above it.
- Search: filename + full text (FTS5), filters by type and tag. Results list with path, type, snippet.
- Preview pane: syntax-highlighted code (QSyntaxHighlighter, Python only is fine), plain text, image thumbnail,
  first-page PDF text. For Office files and anything else: a card with name/size/date and an **Open externally** button.
- Tags and notes: sidecar at `<resources_root>/.staffroom/tags.json` keyed by relative path.
  Tag editor in the preview pane. Never write into the resource files.
- `ResourceService` exposed to plugins: `pick(filter=...) -> Path | None`, `search(q) -> list[Resource]`,
  `open_externally(path)`, `open_for_class(path, label)` (implemented in 1b).
- CLI: `staff library index|search <q>|tags <path>`.

Acceptance:
- Full index of the current root completes in under 60 s and survives cloud-only files.
- Searching "while" returns the Python course while-loop slides' sibling `.py` files and the OCR booklet exercises.
- Tagging a file, restarting, and the tag persists; the resource file's mtime is unchanged.
- Opening a `.pptx` launches PowerPoint/Keynote; the app does not try to parse it.

### 1b. `classroom` tool

Scope:
- "Open for class": copy the selected resource to `<sessions_root>/<YYYY-MM-DD>/<label>/<filename>` and launch
  the configured editor on the copy. Default editor command on macOS: `open -a Thonny {file}`; IDLE and
  "system default" as presets; fully editable in settings.
- `sessions_root` is configurable and defaults to local `~/TeachingSessions`. Never auto-detect or default to a
  cloud-synced folder: which folder is reachable from school is the teacher's call. A folder picker in Settings
  covers syncing elsewhere if wanted. State the folder in the UI.
- Label is free text for the lesson (e.g. "P3 Y9 loops"). Never a class list or pupil names; the field is a single
  short line and the UI says so.
- Session browser: list of past sessions, each with its files; **Diff vs original** (unified diff in a read-only view);
  **Promote** copies the edited file back into the resources root as `<name>_v2.py` (never overwrites);
  **Re-open** relaunches the editor on the copy.
- CLI: `staff classroom open <resource> --label "..."`, `staff classroom list`, `staff classroom diff <session-file>`.

Acceptance:
- Opening a file for class, editing it in Thonny and saving leaves the original byte-identical.
- Diff shows the edit; Promote creates a new file next to the original and the library picks it up on re-index.
- Works with no cloud folder of any kind; the default is plain local.

Out of scope: any built-in code editor. Do not build one.

---

## Phase 2 — `marks`

Scope:
- Input CSV: one column per question (`q1..qn`) with raw marks, one row per script, **no identifier column**.
  Any column whose header looks like an identifier (name, id, upn, candidate, email, class) is dropped with a
  warning before processing. Max marks per question via a first row flagged `MAX` or a sidebar field.
  Fake example data in `examples/`.
- Editable grade-boundary table with presets saved per spec (OCR J277, AQA 8525, A-level) in config.
- Outputs: grade per row, grade distribution (table + bar chart via matplotlib to PNG, shown in the chart widget),
  facility index per question, discrimination (top-third vs bottom-third) per question, "worst five questions".
- Save: aggregates only — distribution, facility and discrimination per question, chart PNG. The per-row table is
  view-only and is never written to disk.
- CLI mirrors the panel.

Acceptance:
- Known fixture produces hand-checked grades and facility indices (write the numbers into the test).
- Boundaries preset round-trips through config.
- Saved outputs contain no per-row data; a fixture with a `Name` column is rejected/dropped with a warning.

---

## Phase 3 — `parsons` + `worksheet` (and the shared docx/PDF house style)

Do the house style first, in `core/export/`: one docx template (python-docx) and PDF (reportlab or docx→pdf via
LibreOffice if present — prefer reportlab so there is no external dependency). Header with title/topic/date,
footer with page number, monospace block style for code, answer-key section that can be split to a second file.

### `parsons`
- Input: a `.py` picked from the library or pasted. Parse with `ast`; split into blocks at statement level
  (option: line level). Shuffle with a seed. Options: number of distractors (generated by mutating a line:
  off-by-one, wrong comparison, missing colon), indentation shown or stripped, include a hint box.
- Output: worksheet docx/PDF + answer key. Preview in panel.
- CLI: `staff parsons make <file> --seed N --distractors K`.

### `worksheet`
- Generators, each a pure function `(seed, count, difficulty) -> list[Question]` in `logic.py`:
  denary↔binary↔hex, two's complement, binary addition with overflow flag, logical/arithmetic shifts,
  truth tables (2–3 inputs, AND/OR/NOT/XOR/NAND/NOR), Boolean simplification with the laws listed step by step,
  file-size calcs (image, sound, text), run-length encoding, Huffman tree weight.
- Output: worksheet + key via the house style. Seed shown on the sheet so a set can be regenerated.
- CLI: `staff worksheet make --topic binary --count 20 --seed 42`.

Acceptance:
- Every generator is property-tested: answers verify by independent computation (e.g. `int(x, 2)`).
- Parsons answer key reconstructs to code that `ast.parse`s and is equal (ignoring blanks) to the input.
- Both tools open their inputs via `ResourceService.pick()`.

---

## Phase 4 — Sandboxed runner + `trace`, `bugs`, `fade`

Do the runner first, in `core/runner/`: run a Python file in a subprocess with `-I`, cwd = temp dir, no network
(macOS: rely on timeout + no sockets imported check via AST; do not pretend this is a security boundary — these
are the teacher's own files), hard timeout, captured stdout/stderr, optional stdin script. Used by all three tools.

- `trace`: instrument via `sys.settrace` in the child, record line number and local variable values per step for
  a configured subset (assignments, loops, ifs, function calls). Output blank and completed trace tables in the
  house style. Cap at N steps.
- `bugs`: AST-based mutations (comparison flip, off-by-one, missing `:` or `)`, wrong variable name, indentation
  slip, string/int confusion). Choose error classes and count; emit N variant files + a key. Each variant is run
  through the runner so the key can say whether it crashes or silently misbehaves.
- `fade`: given a solution, produce K versions with progressively more lines replaced by `____` (bottom-up by
  default, or by chosen line ranges). Output as a sequence in the house style.

Acceptance:
- Runner kills an infinite loop within the timeout and reports it.
- Trace of a known 10-line loop matches a hand-written table in the test.
- Every `bugs` variant differs from the original by exactly the described mutation.

---

## Phase 5 — `pseudocode`

Scope: Python ↔ OCR Exam Reference Language and AQA pseudocode, GCSE subset only (variables, arithmetic, string
ops, if/elif/else, for/while, functions/procedures, lists/arrays, input/output, basic file ops). Implement as
AST → intermediate → target, with an explicit "could not translate" list rather than silent omissions.
Direction toggle, side-by-side text panes, copy button. CLI `staff pseudocode to-ocr|to-aqa|to-python <file>`.

Acceptance: round-trip tests on the OCR Booklet `.py` files in the resources (at least the 1a–8c set):
Python → ERL → Python must produce an AST-equivalent program or list what was dropped.

---

## Phase 6 — `quiz`

- Question bank format: Markdown or YAML files tagged with spec points from the `core/spec/` taxonomy
  (OCR J277, AQA 8525 — ship the taxonomies as data files). Types: MCQ, short answer, true/false.
- Exporters: Kahoot CSV (their template columns), plain text for Forms paste, printable do-now (house style)
  with separate answers.
- Retrieval scheduler: given a "taught" log (topic + date only — no class or pupil data), pick questions from
  topics taught 1, 3 and 6 weeks ago.
- CLI: `staff quiz export --format kahoot --topics ... --n 10`.

Acceptance: Kahoot CSV imports into Kahoot without column errors (manual check, note it); the retrieval scheduler
picks only from topics taught in the configured windows on a fixture log.

---

## Phase 7 — Polish and packaging

- App icon, dark/light theme check on every panel, keyboard shortcuts (⌘K search in library, ⌘O open for class).
- Settings page covers: resources root, sessions root, editor command, spec preset, house-style title/footer text.
- `uv run staffroom` → a `.app` via PyInstaller or briefcase so it sits in the Dock. Only after everything else works.
- Review which of the nine tools were actually used in a month (`staff usage`). Delete or shelve the rest.

---

## Kick-off prompt for each phase

> Read `CLAUDE.md`, `docs/ROADMAP.md` and `docs/PHASES.md`. We are starting **Phase N**. Confirm the previous phase's
> acceptance criteria still pass (run tests and lint). Then give me a plan of at most 15 lines for this phase,
> ask about anything genuinely ambiguous, and build it in the order listed. Finish by running tests and lint,
> showing the CLI output and a screenshot of the panel, and adding a CHANGELOG entry.
