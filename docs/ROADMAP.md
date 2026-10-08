# Staffroom — Roadmap

Nine tools for a UK secondary computer science teacher (KS3, GCSE OCR J277 / AQA 8525, A-level).
Runs on the teacher's Mac. Outputs (PDF, docx, CSV, PNG) are taken into school systems manually.

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

### Engineering rules
- Tools never import Qt. Logic never does I/O. New UI needs go into the shared widget kit.
- The resources folder is read-only to every tool. Edits happen on session copies; tags live in a sidecar.
- This project is standalone. No integration with the author's other apps; no shared data formats.

## Shell-level feature: Resource Library

Not a plugin — a second root in the sidebar ("Tools" / "Resources") exposed to plugins as a service
(`ResourceService.pick()`, `.open_for_class()`, `.search()`).

- Index a configured resources root (a typical department folder: a few hundred .py, .pptx, .doc, .pdf and Scratch files plus txt/csv/images).
- Full-text search across .py/.txt/.md/.csv/.docx/.pptx/.pdf. Legacy .doc/.ppt/.pub need conversion
  (LibreOffice headless or skip with a warning) — do not use python-docx on .doc.
- Filters: type, topic, key stage, tag. Tags and notes in `<root>/.staffroom/tags.json`, never in the files.
- Preview pane: syntax-highlighted code, extracted text for documents, thumbnail for images.
- Hide cruft (Thumbs.db, .DS_Store, zips) by default. Detect iCloud placeholder files (reads fail with
  "Resource deadlock avoided") and mark them cloud-only rather than crashing.
- Incremental re-index on file watcher or on demand.

## The nine tools (build order)

| # | Tool | One-liner | Inputs | Outputs | Panel |
|---|------|-----------|--------|---------|-------|
| 1 | `classroom` | Open a resource for class without touching the original | library file | session copy in `sessions/<date>/<label>/`, launched in Thonny (configurable editor); diff vs original; "promote to new version" | file pick, label, editor dropdown, open button, diff view |
| 2 | `marks` | Class-level marks → grades and question analysis | CSV (q1..qn only, no identifier column) + editable boundaries | grade table, facility index per question, distribution chart, worst-5 questions; saves aggregates only | file picker, boundaries table, run, results table + chart |
| 3 | `parsons` | Working code → Parsons problem worksheet | .py (from library) + options (granularity, distractors, indentation on/off) | docx/PDF worksheet + answer key | file pick, options form, run, preview |
| 4 | `worksheet` | Seeded random theory question sets with keys | topic + count + seed + difficulty | PDF/docx. Topics: binary/hex/denary, two's complement, shifts, binary add, truth tables, Boolean simplification with steps, file-size and sampling calcs, RLE/Huffman | options form, run, preview |
| 5 | `trace` | Code → blank and completed trace tables | .py + optional inputs | docx/PDF; executed via `sys.settrace` in a subprocess with timeout, never in-process `exec` | text/file, inputs box, run, table, export |
| 6 | `bugs` | Inject controlled errors into working code | .py + error types + N | N variant files + teacher key | file pick, checkboxes, run, list |
| 7 | `pseudocode` | Python ↔ OCR ERL / AQA pseudocode (GCSE subset) | text | text + "could not translate" report | text in/out, direction toggle |
| 8 | `quiz` | Author once, export everywhere | YAML/Markdown question bank tagged by spec point | Kahoot CSV, Forms-paste text, printable do-now with answers; retrieval scheduler picks topics taught N weeks ago | file pick, filters, run, preview |
| 9 | `fade` | Worked solution → progressively faded completion problems | .py + steps | docx/PDF sequence | file pick, slider, run, preview |

Build order rationale: `classroom` and the library are used every lesson from day one and nothing else provides them.
`marks`, `parsons`, `worksheet` are the next most frequent. Reassess after a month of real use before building 5–9.

## Shared in `core/` (not in tools)

- Spec-point taxonomy for OCR J277 / AQA 8525 / A-level, used by `quiz`, `worksheet`, library tags.
- One docx/PDF house style for every worksheet and key.
- Sandboxed code runner (subprocess, no network, temp dir, timeout) used by `trace`, `bugs`, `fade`.
- Python subset parser/AST helpers shared by `parsons`, `bugs`, `fade`, `pseudocode`.

## Deliberately not building

- Code editor — Thonny is better for pupils; `classroom` solves the overwrite problem instead.
- Class lists, seating plans, trackers, per-pupil feedback, behaviour/praise logs, MIS imports — pupil data (see Hard rules).
- Teachers' Standards evidence logging — out of scope; this project stays independent of it.
- LMC / sorting visualisers — need custom animated widgets; good web versions exist.
- Exam-paper generator — only pays off once a question bank exists; revisit next year.
