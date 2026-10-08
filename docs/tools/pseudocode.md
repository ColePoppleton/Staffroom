# Pseudocode

Python ↔ OCR Exam Reference Language ↔ AQA pseudocode, for the GCSE subset.
Anything that cannot be translated is kept as a comment in the output and
listed; nothing is dropped silently.

![Pseudocode panel](../pseudocode-dark.png)

The subset: variables, arithmetic (`DIV`, `MOD`, `^`), comparisons,
`AND/OR/NOT`, if/elif/else, count loops, for-each, while, `do…until`,
functions and procedures, lists and indexing, string length / substring /
upper / lower, casts, random, basic file methods, comments. *ERL* and the
other names are in the [Glossary](../guide/glossary.md#pseudocode).

The panel writes the translation as `<stem>.ocr.txt`, `<stem>.aqa.txt` or
`<stem>.py` unless *Save output* is set to `none`; the terminal commands
only write with `--save` ([Outputs](../guide/outputs.md)). On the command
line the source language comes from the file name (`.py` is Python, `.aqa`
anywhere in the name is AQA, any other `.txt` is OCR ERL) unless `--from`
says otherwise, so `to-ocr notes.txt` reports that it cannot translate OCR
to OCR: add `--from aqa`, or use `to-python`. The panel's *Direction* sets
both languages explicitly.

```bash
staff pseudocode to-ocr program.py
staff pseudocode to-aqa program.py --save --out ./out
staff pseudocode to-python sheet.ocr.txt
```
