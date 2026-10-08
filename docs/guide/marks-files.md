# Marks files

One row per script, one column per question, **no identifier column**.

```csv
row,q1,q2,q3,q4,q5,q6
MAX,4,6,8,6,10,6
1,4,6,7,5,9,6
2,4,6,8,6,10,6
```

- Question columns are anything matching `q1`, `Q2`, `q10a`.
- A row with the text `MAX` in any cell gives the max marks per question.
  It needs a non-question column to live in; `row` is fine and is ignored.
- Any column whose header looks like an identifier (name, id, UPN, candidate,
  email, class, form, date of birth and their variants) is dropped on load
  and reported. You cannot turn that off.
- XLSX works the same way (first sheet).
- Commit nothing real. Example files start with a `# FAKE DATA` line and the
  pre-commit hook refuses any CSV or XLSX without it.
