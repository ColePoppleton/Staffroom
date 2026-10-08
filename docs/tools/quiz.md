# Quiz

Write questions once in a Markdown bank tagged with spec points and topics;
export to Kahoot, to text for a Forms quiz, or to a printable do-now with a
separate key. Retrieval mode picks from topics taught one, three and six
weeks ago.

![Quiz panel](../quiz-light.png)

See [Question banks](../guide/question-banks.md) for the file format.

| Format | Produces |
| --- | --- |
| kahoot | `.xlsx` in Kahoot's template layout plus a `.csv` with the same headers |
| forms | numbered text with lettered options and a separate answers block |
| donow | house-style docx and PDF with the key split off |

```bash
tt quiz export --bank bank.md --format kahoot --topics binary,cpu --n 10
tt quiz retrieval --bank bank.md --log taught.csv --date 2026-10-08
tt quiz check --bank bank.md
tt quiz spec ocr
```

!!! note
    The Kahoot import is checked by hand against Kahoot's template columns.
    If Kahoot changes its template, `tt quiz check` will not notice.
