# Quiz

Write questions once in a Markdown bank tagged with spec points and topics;
make a printable do-now with a separate key, a Kahoot import or text for a
Forms quiz from it.

![Quiz panel](../quiz-light.png)

See [Question banks](../guide/question-banks.md) for the file format.

The panel starts from the bank. Choose it (*From library…* or *Browse…*, or *Quiz*
on the Library's use bar when the bank is selected there) and its chip says what
was found in it: *13 questions · 6 topics · OCR and AQA spec points · no
problems*, or the first problem with its line (`staff quiz check` lists them
all). *Preview questions* opens every question in a window.

- **Make**: *Do-now sheet* (the default), *Kahoot* or *Forms text*. The run
  button says which (*Make do-now*).
- **Questions from**: *Topics I pick* shows the bank's own topics as chips,
  each with how many questions carry it; turn on the ones you want (none
  means any topic) and the line under them keeps the total. *Taught 1, 3 and
  6 weeks ago* shows the taught log and the date to count back from instead,
  and says what the log has in each of those weeks and how many questions
  that leaves.
- **Questions** and **Seed** on one row; the spec-point filter and the
  sheet's title are under *More*.

The do-now opens on its *Sheet* page, with the *Key* beside it and the
chosen questions listed under *Chosen questions*; Kahoot and Forms show
their *Paste text* instead of the pages.

| Make | Produces |
| --- | --- |
| Do-now sheet (`donow`) | house-style docx and PDF with the key split off |
| Kahoot (`kahoot`) | `.xlsx` in Kahoot's template layout plus a `.csv` with the same headers |
| Forms text (`forms`) | numbered text with lettered options and a separate answers block |

Files are named after the bank, the kind of sheet and the seed:
`<bank>_kahoot_s1.xlsx` and `.csv`, `<bank>_forms_s1.txt`,
`<bank>_donow_s1.docx` / `.pdf` and `<bank>_donow_s1_key`. A retrieval run
adds the date it picked for, `<bank>_retrieval_2026-10-08_donow_s1.pdf`, so
it never replaces the do-now made before it. A run that does replace a file
of the same name (same bank, kind, date and seed) says so: a warning in the
result strip, and the summary; change the seed to keep both ([Outputs](../guide/outputs.md)).
Questions from *Taught 1, 3 and 6 weeks ago* (the command line's `quiz
retrieval`) looks at the topics taught one, three and six weeks ago, each with three days' leeway, and draws
questions round-robin across the three windows; the run log lists what fell
in each, and names any taught-log column other than `date` and `topic` as
dropped (an identifier, such as a name or class) or ignored, by header only
([Taught log](../guide/question-banks.md#taught-log-for-retrieval-mode)).
*Do-now*, *spec point* and *retrieval windows* are in the
[Glossary](../guide/glossary.md#quiz).

## Short answers in Kahoot

Kahoot has no typed-answer question, so a `short` question becomes a
four-option one: the real answer plus three distractors borrowed from the
other short answers in the bank (the whole bank, not only the questions
chosen). The nearest are taken first: short answers with the same `topic:`
tag, then ones in the same spec section (`ocr:1.2.x` for an `ocr:1.2.4`
question), then anywhere. When a distractor had to come from outside the
topic the run log says where from, for example
`Q12: distractors borrowed outside topic 'networks': '10' (Q5, binary), …`,
so you can add a few more short answers on that topic if it reads oddly.

A short answer with fewer than three distinct distractors available anywhere
in the bank is left out of the Kahoot file, and so is an mcq whose only
correct option is the fifth or later. The summary and the chosen-questions
table describe the file that was written, not the pick:
`3 of 5 written; 2 short answers skipped: Q5, Q7 → …`, and each skipped
question is a warning in the result strip with its reason (so are clipped text,
dropped options and distractors borrowed from another topic). If nothing could be written the export stops with a message
instead of leaving an empty file.

On the command line `export` still makes a Kahoot file unless `--format`
says otherwise:

```bash
staff quiz export bank.md --format donow --topics binary,cpu --n 10
staff quiz retrieval bank.md --log taught.csv --date 2026-10-08
staff quiz check bank.md
staff quiz spec ocr
```

!!! note
    The Kahoot import is checked by hand against Kahoot's template columns.
    If Kahoot changes its template, `staff quiz check` will not notice.
