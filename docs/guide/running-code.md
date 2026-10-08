# Running pupil code

**Trace** and **Bugs** run the program you give them. **Fade** does not run
anything: it blanks lines out of the solution as text.

A run happens in a separate Python process, started by the app with these
limits. They are there to stop an accident (a loop that never ends, a print
flood) from freezing your Mac. They are **not a security boundary**: the file
is one you chose, written by you or copied from a pupil, and you would run it
in Thonny anyway.

## What a run gets

- **A time limit.** Trace allows 10 seconds, Bugs 4 seconds per variant.
  When it is up the process is killed and the sheet or the log says
  *timed out (infinite loop?)*. A CPU limit of the same size backs it up.
- **An output cap of 1 MB** (1024 KB) each for what the program prints and
  for its error messages. Anything past the cap is read and thrown away, so
  the app's memory stays flat however much the program prints. Capped
  output ends with the line `[output truncated at 1024 KB]`, the run is
  described as *output capped at 1024 KB* in the log, and the trace key
  or the bugs key says so. Trace also caps what it collects inside the run
  at 1 MB, so a `while True: print(i)` traced for 10 seconds stays small.
- **A fresh, temporary working folder** that is deleted afterwards, a
  minimal environment, and `python -I` (no site packages, no `PYTHON*`
  variables from your shell). Inputs you type in the *Inputs* box are fed
  to `input()`; when they run out, `input()` raises `EOFError`.
- **A refusal to run files that import** networking or process modules:
  `socket`, `ssl`, `http`, `urllib`, `requests`, `subprocess`,
  `multiprocessing` and friends. The check reads the source before running
  it and also recognises `__import__("socket")` and
  `importlib.import_module("socket")` when the module name is written out
  as a string.

## What a run does not stop

- `os.system("…")`, `os.popen` or anything else in `os` that reaches the
  shell. The import check is a list of module names, not a sandbox.
- Writing, moving or deleting files anywhere your account can. The working
  folder is temporary; the rest of the disk is not hidden.
- An import whose name is built at run time, such as
  `__import__("soc" + "ket")`. The check is best effort by design.
- Memory. A program that builds a huge list can still use a lot of it until
  the time limit kills the process.

If a file came from somewhere you do not trust, read it before you run it,
exactly as you would before running it on the board.

## Why not a real sandbox

Containers, seccomp or network namespaces would cost a great deal, still
would not be a boundary on macOS, and would protect against the wrong
thing: these are your own files. The audit that raised this (decision #6,
`docs/audits/2026-10-08.md`) chose to cap the output and write the limits
down instead.
