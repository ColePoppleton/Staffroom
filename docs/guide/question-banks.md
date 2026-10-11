# Question banks

A bank is a Markdown file. One `## ` heading per question; the lines under it
are fields. [`examples/question_bank.md`](https://github.com/ColePoppleton/Staffroom/blob/dev/examples/question_bank.md)
is a complete example.

```markdown
# Any title

## What does CPU stand for?
type: mcq
tags: ocr:1.1.1, aqa:3.4.4, topic:cpu
time: 20
- [x] Central Processing Unit
- [ ] Central Program Utility
- [ ] Computer Personal Unit
- [ ] Core Processing Utility
why: The CPU fetches, decodes and executes instructions.

## RAM is volatile.
type: tf
tags: topic:memory
answer: true

## What is 1010 in denary?
type: short
tags: ocr:1.2.4, aqa:3.3.2, topic:binary
answer: 10
```

| Field | Meaning |
| --- | --- |
| `type` | `mcq`, `short` or `tf`. Defaults to `mcq` when options are present, else `short`. |
| `tags` | Comma-separated. `ocr:1.2.4` / `aqa:3.3.4` are spec points (`staff quiz spec ocr` lists them); `topic:...` tags drive filters and retrieval. |
| `- [x]` / `- [ ]` | Options for an mcq; `x` marks a correct one (several allowed). |
| `answer` | The answer for `short`; `true` or `false` for `tf`. |
| `time` | Seconds for Kahoot (snapped to 5, 10, 20, 30, 60, 90, 120 or 240). |
| `why` | Explanation, printed in the do-now key. |

`staff quiz check --bank bank.md` reports every problem with its line number and
any spec tag that is not in the taxonomy.

## Taught log (for retrieval mode)

A CSV with `date,topic` columns. Topic and date only, never a class or a
pupil. Start it with `# FAKE DATA` if it is an example you intend to commit.
It is read like every other table, so a column that could identify a pupil
(a name, a class, an id) is dropped as the file is loaded, and the panel and
the run log say so by header only (`Never read: Class (could name a pupil)` in the panel, `dropped identifier
column(s), never read: Class` in the log).
Any other extra column is ignored and named once by its header
(`ignored column 'room' — the log is date and topic only`). What either kind
of column holds is never read or shown. Take it out of the file.

```csv
date,topic
2026-09-17,loops
2026-09-24,searching
```
