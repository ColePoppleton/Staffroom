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

## What the identifier filter catches, and what it does not

Every table any tool loads (`core/privacy.py`, applied by the shared reader
in `core/csvio.py`) has its identifier columns removed before a tool, a
preview or an output sees it. A column is an identifier when **any whole
word of its header** is one of these, or when the header with spaces and
punctuation removed is one of the joined forms:

| Kind | Header words that drop the column |
| --- | --- |
| Names | `name`, `names`, `forename(s)`, `surname(s)`, `firstname`, `lastname`, `fullname`, `nickname`, `initials` |
| Who | `pupil(s)`, `student(s)`, `learner(s)`, `child`, `candidate(s)`, `cand` |
| Numbers | `id`, `ids`, `identifier`, `upn`, `uln`, `adno`, `admission` |
| Contact | `email(s)`, `mail`, `username`, `login`, `photo` |
| Grouping | `class(es)`, `form`, `tutor`, `tutorgroup`, `formgroup`, `set`, `group` |
| Dates | `dob`, `birth`, `birthday` |
| Joined forms | `studentid`, `candidateno`, `candidatenumber`, `dateofbirth`, `classcode`, `teachinggroup`, `reggroup`, `pupilname`, `surnameforename` and the like |

Words are split on spaces, punctuation and camelCase, so `Candidate Number`,
`student_id`, `studentId` and `Class` all go; `q1`, `Total` and `classwork`
stay. The header words are the test, not the values: a column headed
`Comment` full of names is **not** caught.

What passes through:

- **Per-pupil flag columns** such as `SEN`, `PP`, `EAL`, `FSM`, `Gender`,
  `Target`, `Behaviour`, `Postcode`, `Reg` and `Adm No` (only `adno` is
  listed). They are not identifiers on their own, so they reach the preview
  table. **Marks** ignores every non-question column and never saves a row,
  so nothing from them persists; but they are on screen while the tool is
  open, and they describe individuals. Take them out of the export before
  you load it.
- **Any column the header does not give away.** The filter is a list of
  header words, not a reading of the cells.
- The `set` and `group` words also drop columns you might have meant, such
  as `Question set`. Rename the column if that happens; the log and the
  preview caption tell you which were dropped.

The marks file format, with examples, is in [Marks files](marks-files.md).

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

## What the log contains

There are two logs, and neither holds a value from your files.

**The run log** under each tool's results (the launcher) or on stderr (the
terminal) is what the tool said while it worked: the names of dropped
identifier columns (*"Dropped identifier column(s), never used: Name,
Candidate Number"*), its warnings (a mark above the max, blank cells
counted as 0, a run that timed out or hit the output cap), what each bugs
variant did, which quiz topics fell in each retrieval window, and the
editor command Classroom launched. It is shown, not saved.

**The app log** is the log drawer in the launcher (⌘L) and a file,
`~/.config/staffroom/logs/staffroom.log`. The file rotates at 512 KB and
keeps three older copies (`staffroom.log.1` to `.3`), so the folder never
grows past about 2 MB; `staff` prints the same lines to stderr. If the
config folder cannot be written (a locked-down school account), the file is
skipped: one warning line says so, the run carries on, and the log goes to
stderr only. The Resource Library does the same with `library.db`: one
warning line, *Resource Library unavailable: cannot write …* in the
Library and in `staff library status`, search on the last index
read-only (or none, if there is no earlier index), no indexing, and every
tool still runs. Each line is a time, a level, the module and a message, and the
messages hold:

- which tool started and finished, with its one-line summary (*"12 scripts
  graded; aggregates saved to …"*);
- the **paths** of files read, written, copied or promoted;
- the **names of dropped identifier columns**, again (*"marks.csv: dropped
  identifier column(s) Name, Candidate Number"*): the headers, never a
  value from the column;
- the library's index summaries (file counts, how many were indexed by name
  only, and the relative path of each of those files);
- one line per failed run, saying which tool and the message you saw.

Never in either log: a cell from a marks file, a line of a resource's text,
a pupil's work. The level is set in *Settings › Logging* (`INFO` by default;
`DEBUG` adds detail about the app, not about your files). The file does
contain file paths, so if your folders are named after classes, so is the
log.

## Where things live

Everything Staffroom writes to your Mac, found by listing the disk after a
full session of using every tool.

| Store | Path | Holds |
| --- | --- | --- |
| Config | `~/.config/staffroom/config.toml` | settings only: theme, folders, editor command, exam board, header and footer text, the library exclusion list |
| Library index | `~/.config/staffroom/library.db` | path, size, modified time and kind for every file under the resources folder, and the text of searchable files except those indexed by name only |
| Log | `~/.config/staffroom/logs/staffroom.log` (+ `.1` to `.3`) | tool names, file paths, names of dropped columns, warnings; never values |
| Usage | `~/.config/staffroom/usage.toml` | run count (launcher and `staff` commands, with the CLI's share) and last-used date per tool; never what was run on |
| Lesson copies | `<sessions folder>/<date>/<lesson label>/` | the copy you edited in class |
| Session sidecar | `<sessions folder>/<date>/<lesson label>/.origin.json` | the lesson label and, for each copy, the absolute path of the original it came from |
| Tag sidecar | `<resources folder>/.staffroom/tags.json` | tags and notes keyed by the resource's relative path |
| Ignore file | `<resources folder>/.staffroom/ignore` (optional, yours) | exclusion patterns, one per line |
| Tool outputs | next to the input; `<sessions folder>/outputs/<tool>/` when there is no input file; or the folder you set | sheets and keys, aggregate CSVs and the chart, variant `.py` files, quiz exports: see [Outputs](outputs.md) |

The sessions folder is `~/TeachingSessions` unless you change it. The
lesson label is the one line you typed (60 characters at most); the UI asks
for a lesson, not a class, and cannot check what you wrote.

!!! note "Upgrading from Teaching Tools"
    The first run of Staffroom copies `~/.config/teaching-tools/` to
    `~/.config/staffroom/` and leaves the old folder alone. A
    `.teaching-tools/tags.json` sidecar (or `ignore` file) in the resources
    folder is still read; the next edit writes `.staffroom/tags.json`.

Nothing leaves the machine. The app checks its git remote for updates when
started from a checkout, and that is the only network call it makes.

## Deleting everything

There is no account and no server, so removing the app's traces is a
matter of deleting folders:

1. `~/.config/staffroom/` (config, logs, the library index, usage counts),
   and `~/.config/teaching-tools/` if it is still there from before the
   rename.
2. The sessions folder (`~/TeachingSessions` by default), which holds the
   lesson copies, their `.origin.json` sidecars and the default outputs
   folder.
3. `<resources folder>/.staffroom/` (tags, notes, your ignore file) and any
   `.teaching-tools/` folder beside it. The resources themselves were never
   changed.
4. Any outputs you saved next to inputs or in a folder you chose.

Then `uv tool uninstall staffroom`, or drag the launcher app out of
/Applications.

## In the repository

Example files are invented and carry a `# FAKE DATA` first line; a
pre-commit hook refuses any CSV or XLSX without it. Tests that need data
make it up.
