# Parsons

A working program → a worksheet of shuffled blocks to put back in order,
with optional distractors, and a key.

![Parsons panel](../parsons-dark.png)

- **Split at** *Statements* (compound headers and their bodies become
  separate blocks, so structure is rebuilt too) or *Lines*.
- **Distractors** are real lines with one mistake a pupil can spot from the
  sheet: a colon removed, a comparison changed (`<` to `<=`, `==` to `!=`…;
  the key says *wrong comparison*), a number off by one in a `range()`, an
  index or a `while` condition, or a wrong variable. A wrong
  variable is another of the program's own variables of the same sort,
  already set when the line runs (`total = total + count` for
  `total = total + score`), never a list for a number or a name the line
  could not use yet. Data is never changed: list values, a variable's
  starting value, the number in an `if` and strings stay as written, and no
  distractor adds `+ 0`. A program with none of these gets fewer distractors
  than asked for. The key says which blocks to leave out, the real line each
  one looks like, and what is wrong with it.
- **Show indentation** off makes pupils decide the indents.
- **Include a hint box** (on by default) prints a short starting hint above
  the blocks.
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
