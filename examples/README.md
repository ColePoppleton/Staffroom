# Examples

Small **invented** data files for trying tools and for tests. Every file starts
with a `# FAKE DATA` marker row; the pre-commit hook refuses CSV/XLSX files
without one, so real pupil data can never be committed by accident.

| File | Purpose |
| --- | --- |
| `class_list.csv` | Ten made-up pupils with class and target grade. Used by `hello`. |
| `marks_10x.csv` | Per-question raw marks on a 40-mark paper, for the future `marks` tool. |
