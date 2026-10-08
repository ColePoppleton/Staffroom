# Fade

A worked solution → K versions with progressively more lines blanked to
`________`, for faded-example practice. Bottom-up by default, top-down, or
only the line ranges you choose. `def`/`if`/`for`/`while` headers stay unless
you say otherwise. The key is the complete program. Every version has at least one more blank
than the one before, so you get at most one version per fadeable line: ask for
8 versions of a 2-line program and you get 2, with a note in the log. Lines
listed in a range that are headers, comments or blank are skipped with a note;
a line past the end of the file, or a file that is not valid Python, stops the
run with a message saying which line. Nothing is run: the
solution is blanked out as text (see [Running pupil
code](../guide/running-code.md) for the tools that do run it).

Files: `<stem>_faded.docx` / `.pdf` holds every version, `<stem>_faded_key`
the complete solution ([Outputs](../guide/outputs.md)). *Faded example* and
the other terms are in the [Glossary](../guide/glossary.md#sheets).

```bash
staff fade make solution.py -k 4 --order bottom_up
staff fade make solution.py -k 2 --order ranges --ranges 3-5,8
```
