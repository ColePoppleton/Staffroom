# Parsons

A working program → a worksheet of shuffled blocks to put back in order,
with optional distractors, and a key.

![Parsons panel](../parsons-dark.png)

- **Split at** statement (compound headers and their bodies become separate
  blocks, so structure is rebuilt too) or line.
- **Distractors** are real lines with one mistake a pupil can spot from the
  sheet: a colon removed, a comparison flipped, or a number off by one in a
  `range()`, an index or a `while` condition. Data is never changed: list
  values, a variable's starting value and the number in an `if` stay as
  written, and no distractor adds `+ 0`. A program with none of these gets
  fewer distractors than asked for. The key says which blocks to leave out
  and what is wrong with each.
- **Show indentation** off makes pupils decide the indents.
- The sheet prints the blocks as numbered cut-out boxes, two across, with
  dashed cut lines and an answer grid underneath; a 15-block problem fits on
  one A4 page.
- The key reconstructs the program; the tests prove it is equivalent to the input.
- The seed is in the file name and on the sheet, so the same shuffle can be
  made again.

Files: `<stem>_parsons_s<seed>.docx` / `.pdf` and `…_key`
([Outputs](../guide/outputs.md)). *Parsons problem*, *distractor* and *seed*
are in the [Glossary](../guide/glossary.md#sheets).

```bash
staff parsons make program.py --seed 7 --distractors 2 [--lines] [--no-indent]
```
