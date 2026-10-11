# Bugs

Inject one controlled error per copy of a working program. Pupils find the
line and predict what happens; the key knows, because each variant was run.

![Bugs panel](../bugs-light.png)

The program is shown on the left, numbered; click a row of the key and the
line that variant broke lights up in it.

Error classes: comparison flipped, off by one, missing colon, missing
bracket, wrong variable name, indentation slip, string / integer confusion.
Each variant differs from the original by exactly one line, and the key says
*crashes: SyntaxError*, *runs, but the output is wrong*, *hangs*, or
*silent: no visible change*.

A bug that leaves the program running exactly as before cannot be found by
running it, so by default the tool runs each candidate while choosing and
skips silent ones for the next bug in the seed's order. *Silent bugs
allowed* (`--silent N`) keeps up to N of them for a read-the-code
discussion; each one is marked on the pupil sheet *this version may run
the same: read the code*. The seed is printed in the sheet's header, and
the same seed gives the same versions.

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
