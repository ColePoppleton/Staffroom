# Marks

Raw marks per question, one row per script, **no names** → grades, a
distribution table and chart, facility and discrimination per question, and
the questions to reteach. Only class-level aggregates are ever saved.

![Marks panel](../marks-dark.png)

## Input file

A CSV or XLSX with question columns `q1`, `q2`, … (see
[Marks files](../guide/marks-files.md)). Max marks come from a row flagged
`MAX`, from the *Max marks* option, or, with a warning, from the highest
mark seen. Identifier columns are dropped on load.

## Boundaries

An editable grid of grade and minimum (percent of the paper or raw marks).
Built-in presets for OCR J277, AQA 8525 and A-level are starting points:
edit them to the published boundaries and *Save as preset*.

## Outputs

| On screen | Saved |
| --- | --- |
| Per-script grades (view only) | never |
| Grade distribution | `<stem>_distribution.csv` and `.png` |
| Per-question analysis, worst five | `<stem>_questions.csv` |

Facility is the mean mark as a fraction of the max; discrimination is the
difference between the top and bottom third's mean, over the max.

```bash
tt marks run marks.csv --preset "OCR J277 (GCSE 9-1)" --unit percent --max 4,6,8,6,10,6
tt marks presets
```
