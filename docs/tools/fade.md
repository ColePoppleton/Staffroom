# Fade

A worked solution → K versions with progressively more lines blanked to
`________`, for faded-example practice. Bottom-up by default, top-down, or
only the line ranges you choose. `def`/`if`/`for`/`while` headers stay unless
you say otherwise. The key is the complete program. Nothing is run: the
solution is blanked out as text (see [Running pupil
code](../guide/running-code.md) for the tools that do run it).

Files: `<stem>_faded.docx` / `.pdf` holds every version, `<stem>_faded_key`
the complete solution ([Outputs](../guide/outputs.md)). *Faded example* and
the other terms are in the [Glossary](../guide/glossary.md#sheets).

```bash
staff fade make solution.py -k 4 --order bottom_up
staff fade make solution.py -k 2 --order ranges --ranges 3-5,8
```
