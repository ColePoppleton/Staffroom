# Privacy

This project stores and processes **no personally identifiable pupil data**.
Not as a policy, as a design: there is no tool that accepts a class list,
a name, a candidate number or a seating plan.

## What that means in practice

- **Marks** takes rows of raw marks with no identifier column. Any column
  whose header looks like an identifier (name, id, UPN, candidate, email,
  class, form, date of birth and their variants) is **dropped on load** by
  the shared CSV reader, logged, and shown in the preview caption. No tool
  can opt out. Only aggregates are ever written: distributions, per-question
  facility and discrimination, the chart. The per-script table is view-only.
- **Classroom** records a lesson label (one short line) and the date. The
  field says so.
- **Quiz** retrieval uses a log of *topic and date*, nothing else.
- **Usage** records which tool ran and when, for the monthly "what do I
  actually use" review. Not what it ran on.
- The **Resource Library** indexes your resources folder in place; it only
  ever reads it (Classroom's *Promote* adds a new file beside the original,
  never overwriting). What it keeps, and how to keep things out of it, is
  spelled out below.

## What the Resource Library stores

The library is the one place where the promise depends partly on what you
keep in a folder, so here is exactly what happens.

- **What is indexed.** File names for every file under the resources folder,
  plus the text of `.py`, `.txt`, `.md`, `.csv` and `.pdf` files (the first
  20 pages of a PDF, up to 200,000 characters per file). Nothing else is
  opened: Office files, images, Scratch projects and archives are listed by
  name and opened in their own app.
- **Where it lives.** One SQLite database, `~/.config/staffroom/library.db`.
  Nothing is sent anywhere.
- **The folder is only read.** Tags and notes go in
  `<resources folder>/.staffroom/tags.json`; no resource is ever written to.
- **Keeping folders out.** *Settings › Resources folder › Exclude from the
  library* takes folder names, patterns or paths from the root (`Pupil work`,
  `*assessment*`, `Year 11/Mocks`). The same patterns can be put, one per
  line, in `<resources folder>/.staffroom/ignore` for a folder shared between
  machines (the app reads that file; it never creates it). Excluded paths
  are neither indexed nor listed, and changing the list re-indexes.
  From the terminal: `staff library exclude --add "Pupil work"`.
- **Files that look like pupil details.** At index time, a file whose text
  has an identifier label next to a value (`Candidate number: 4021`,
  `Surname: …`, a UPN, a date of birth) is indexed by **name only**: its text
  is not copied into the database. The index summary, the sidebar status and
  `staff library status` report how many (*"3 files skipped for text: they
  look like they hold pupil details…"*), and the preview says so for each
  one. This is a warning, not a filter you can rely on: a file with a name in
  a comment and nothing else will not be caught. Keep pupil work out of the
  resources folder, or exclude the folder it is in.
- **Deleting the index.** Delete `library.db`, or change the resources folder
  in Settings: the full re-index that follows drops every entry from the old
  folder. Both are tested.

## Where things live

| What | Where |
| --- | --- |
| Config, logs, library index, usage counts | `~/.config/staffroom/` |
| Lesson copies | `~/TeachingSessions/` (or the folder you choose) |
| Tags and notes on resources | `<resources folder>/.staffroom/tags.json` |
| Library exclusion list | `config.toml` (`library_exclude`) and, optionally, `<resources folder>/.staffroom/ignore` |
| Tool outputs | next to the input, or your output folder |

!!! note "Upgrading from Teaching Tools"
    The first run of Staffroom copies `~/.config/teaching-tools/` to
    `~/.config/staffroom/` and leaves the old folder alone. A
    `.teaching-tools/tags.json` sidecar in the resources folder is still
    read; the next edit writes `.staffroom/tags.json`.
| Tool outputs | next to the input, `~/TeachingSessions/outputs/<tool>/` when there is none, or your output folder |


    `.teaching-tools/tags.json` sidecar (or `ignore` file) in the resources
    folder is still read; the next edit writes `.staffroom/tags.json`.

Nothing leaves the machine. The app checks its git remote for updates when
started from a checkout, and that is the only network call it makes.

## In the repository

Example files are invented and carry a `# FAKE DATA` first line; a
pre-commit hook refuses any CSV or XLSX without it. Tests that need data
make it up.
