# Marks

Raw marks per question, one row per script, **no names** → grades, a
distribution table and chart, facility and discrimination per question, and
the questions to reteach. Only class-level aggregates are ever saved.

![Marks panel](../marks-dark.png)

## Input file

A CSV or XLSX with question columns `q1`, `q2`, … (see
[Marks files](../guide/marks-files.md)). Max marks come from a row flagged
`MAX` (the word can be in any cell, including a name column that is about
to be dropped), from the *Max marks* option, or, with a warning, from the
highest mark seen. Identifier columns are dropped on load; what that catches
and what it does not is in [Privacy](../guide/privacy.md#what-the-identifier-filter-catches-and-what-it-does-not).

## Warnings

The run log warns, before you trust the numbers, when:

- a question has a max of 0 (its facility and discrimination are reported
  as 0: check the `MAX` row or the *Max marks* option);
- a script scored above a question's max;
- cells are blank or non-numeric (`ab` for absent, `-`, an empty cell). They count as
  0 in that script's total and grade and are left out of facility and
  discrimination, and the distribution table gains a last row,
  **Incomplete scripts**, saying how many scripts were affected. The chart
  leaves that row out;
- a grade boundary is above the paper total, which is what a percent preset
  applied with the unit set to raw marks looks like.

Nothing in the list stops the run. `examples/marks_messy.csv` makes every
warning fire if you want to see them.

![Marks run on the messy example: every warning in the log](../marks-warnings-light.png)

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

The chart is drawn for paper and slides, white background whatever theme
the launcher is using, so it can go straight into a report.

![Distribution chart](../marks-chart.png)

Facility is the mean mark as a fraction of the max; discrimination is the
difference between the top and bottom third's mean, over the max. Both are
spelled out in the [Glossary](../guide/glossary.md#assessment). Files go
next to the input unless Settings says otherwise ([Outputs](../guide/outputs.md)).

```bash
staff marks run marks.csv --preset "OCR J277 (GCSE 9-1)" --unit percent --max 4,6,8,6,10,6
staff marks presets
```
