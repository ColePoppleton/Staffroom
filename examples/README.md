# Examples

Small **invented** data files for trying tools and for tests. Every file starts
with a `# FAKE DATA` marker row; the pre-commit hook refuses CSV/XLSX files
without one.

Nothing here identifies a pupil, and nothing ever will: see the hard rules in
`CLAUDE.md`. Marks files are one row per script with question columns only.

| File | Purpose |
| --- | --- |
| `marks_10x.csv` | Ten rows of raw marks on a 40-mark paper (q1..q6, max 4,6,8,6,10,6). Used by `hello`. |
| `question_bank.md` | Thirteen invented quiz questions tagged with OCR / AQA spec points and topics, for `quiz`. |
| `taught_log.csv` | A date,topic log (no classes, no pupils) for the retrieval scheduler. |
| `marks_10x_max.csv` | The same marks with an opaque `row` number and a first row flagged `MAX` giving the max per question. Used by `marks`. |
| `marks_messy.csv` | Five scripts with the faults a real markbook has: a mark over the max, a `MAX` of 0, blank cells and `ab` for absent. Every `marks` warning fires on it. |
| `year9.py` | An invented thirteen-line program (a list, a loop, an if/else, prints) for trying `parsons`, `bugs`, `trace`, `fade` and `pseudocode`; the print-layout tests measure its sheets. |
