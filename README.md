# Staffroom

A launcher for small Python tools for UK secondary computing teachers. One desktop shell (PySide6) lists installed tools in a
sidebar; each tool is a plugin that owns its logic and a declarative panel.

## Install

Staffroom is not on PyPI. Install the latest release straight from GitHub with
[uv](https://docs.astral.sh/uv/), then start the launcher:

    uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@v0.8.1
    staffroom

No GitHub account is needed. See [Install](https://colepoppleton.github.io/Staffroom/guide/install/)
for the details and the alternatives.

## Develop

    just setup      # install everything
    just test       # run tests
    just gui        # open the launcher
    uv run staff list  # list tools from the CLI
    uv run staff library index && uv run staff library search while

The launcher's sidebar groups the tools by the teacher's week (Lessons,
Sheets & quizzes, From a program, After a test), with the **Library** first
(search, preview and tag the teaching resources folder; Office files open
externally and are never parsed).

`just install` puts a thin launcher in /Applications that runs this checkout;
`staff update` (or Settings › Update now) pulls the latest code. Shortcuts: ⌘K
library search, ⌘O open for class, ⌘1–9 tools in sidebar order, ⌘L log,
⇧⌘L theme, ⌘, settings.

Documentation: https://colepoppleton.github.io/Staffroom/ (built from
`docs/` by MkDocs). MIT licensed.

See the [contributing guide](https://colepoppleton.github.io/Staffroom/contributing/) for the rules
and `docs/adding-a-tool.md` for how to add
a tool.
