# Pseudocode

Python ↔ OCR Exam Reference Language ↔ AQA pseudocode, for the GCSE subset.
Anything that cannot be translated is kept as a comment in the output and
listed; nothing is dropped silently.

![Pseudocode panel](../pseudocode-dark.png)

The source is on the left, numbered, with the language it is in; the
translation is on the right, numbered too, with what could not be translated
listed under it. Choose a file from the Library or with *Browse…*, or
*Paste instead*.

The subset: variables, arithmetic (`DIV`, `MOD`, `^`), comparisons,
`AND/OR/NOT`, if/elif/else, count loops, for-each, while, `do…until`,
functions and procedures, lists and indexing, string length / substring /
upper / lower, casts, random, basic file methods, comments. *ERL* and the
other names are in the [Glossary](../guide/glossary.md#pseudocode).

The panel writes the translation as `<stem>.ocr.txt`, `<stem>.aqa.txt` or
`<stem>.py` unless *Save output* is set to *Don't save*; the terminal commands
only write with `--save` ([Outputs](../guide/outputs.md)).

**Which language the input is in** is worked out from the code itself
unless you say: `def`, `elif` and lines ending in `:` mean Python;
`endif`, `next i`, `then`, `procedure` mean OCR ERL; `←`, `OUTPUT`,
`USERINPUT`, `ENDWHILE` mean AQA. Words inside strings and comments do not
count. When the code alone does not settle it, the file name is tried
(`.py` is Python, `.aqa` or `.ocr` anywhere in the name names that board).
The run log says what was decided ("Treated input as AQA pseudocode
(guessed from the code)") and the result strip ends *input read as AQA
pseudocode*. Two cases stop with a message instead
of guessing wrong: code with nothing to go on (`x = 5` is all three
languages), and code that already looks like the language asked for, such
as `to-ocr sheet.txt` on an OCR sheet. Both say which `--from` to pass. On
the command line `--from python|ocr|aqa` always wins. In the panel,
*Language* (under the file) switches to the language it guessed as soon as
you choose a file or paste code, so you see the guess before you translate,
and you can set it yourself; it shows *Guess* only when there is nothing to
go on. *To* is the target; if the code is already in that language, *To*
moves to another one.

```bash
staff pseudocode to-ocr program.py
staff pseudocode to-aqa program.py --save --out ./out
staff pseudocode to-python sheet.ocr.txt
staff pseudocode to-ocr notes.txt --from aqa   # when the guess needs overriding
```
