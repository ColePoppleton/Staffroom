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
  never overwriting).

## Where things live

| What | Where |
| --- | --- |
| Config, logs, library index, usage counts | `~/.config/teaching-tools/` |
| Lesson copies | `~/TeachingSessions/` (or the folder you choose) |
| Tags and notes on resources | `<resources folder>/.teaching-tools/tags.json` |
| Tool outputs | next to the input, or your output folder |

Nothing leaves the machine. The app checks its git remote for updates when
started from a checkout, and that is the only network call it makes.

## In the repository

Example files are invented and carry a `# FAKE DATA` first line; a
pre-commit hook refuses any CSV or XLSX without it. Tests that need data
make it up.
