# Bugs

Inject one controlled error per copy of a working program. Pupils find the
line and predict what happens; the key knows, because each variant was run.

![Bugs panel](../bugs-light.png)

Press **Make variants**. *What each bug does* has one card per version
(*Version 2*, *line 9*, *wrong variable name*), with what happens as a badge on the right (red for a crash
or a hang, amber for a wrong output), and the line as it *was* and as it is
*now* underneath. The badge is in view at any window width. The program is
shown on the left, numbered; click a card (or move with the arrow keys) and
the line that version broke lights up in it, and click a line to find the
versions that broke it. The printed sheet and key are unchanged.

Error classes: comparison flipped, off by one, missing colon, missing
bracket, wrong variable name, indentation slip, string / integer confusion.
Each variant differs from the original by exactly one line, and the key says
*crashes: SyntaxError*, *runs, but the output is wrong*, *hangs (infinite
loop)*, or *silent: no visible change (still runs the same)*, which has a
grey badge.

A *wrong variable name* bug swaps in a name a pupil might really type: one
that already holds the same sort of value (a number for a number, a string
for a string) and is assigned earlier in the same function or program, the
most recently assigned first. So `if average >= 50:` becomes
`if count >= 50:`, which runs with the wrong answer, rather than
`if scores >= 50:`, which only crashes. With nothing like it in scope the
name is misspelt instead (`scores` → `score`).

The key's *Original* and *Changed to* columns (*was* and *now* on the cards)
trim each line's indentation,
except where the indentation is the bug: there each space shows as `·`
(`····count = count + 1` → `count = count + 1`) and the *Bug* column says how
far it moved, *indentation slip (4 spaces to 0)*.

A bug that leaves the program running exactly as before cannot be found by
running it, so by default the tool runs each candidate while choosing and
skips silent ones for the next bug in the seed's order. *Silent bugs
allowed* (`--silent N`) keeps up to N of them for a read-the-code
discussion; each one is marked on the pupil sheet *this version may run
the same: read the code*. The seed is printed in the sheet's header, and
the same seed gives the same versions.

The tool also aims for a mix of outcomes. With two or more versions, at
least one *runs, but the output is wrong* (the most useful kind to hunt
for) when the program has such a bug, and at most one stops with a
*SyntaxError* before it starts; a further SyntaxError is used only when
nothing else is left to make up the number. A program that cannot offer
the mix still gets its sheet, and a warning says what is missing.

The sheet puts two versions on each page, each with its *Line / What is
wrong / What happens* line underneath, so four versions print on two pages.

Each run has a 4 second limit and a 1 MB cap on output; a variant that
prints past the cap is marked *output capped*. The runs are not a security
sandbox: see [Running pupil code](../guide/running-code.md).

Files: one `<stem>_bug1.py` … `<stem>_bugN.py` per variant (so a variant can
be opened in Thonny as it is), then the sheet `<stem>_bugs.docx` / `.pdf`
and its `<stem>_bugs_key` ([Outputs](../guide/outputs.md)). If fewer
distinct one-line mutations exist than you asked for, or fewer that change
what the program does, you get fewer and a warning says so.

```bash
staff bugs make program.py -n 4 --seed 1 --kinds missing_colon,off_by_one --stdin "Apple"
staff bugs make program.py -n 4 --silent 1     # keep one bug that runs the same
staff bugs kinds
```
