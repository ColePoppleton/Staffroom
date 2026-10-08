# Staffroom

A launcher for small Python tools for UK secondary computing teachers. One desktop shell (PySide6) lists installed tools in a
sidebar; each tool is a plugin that owns its logic and a declarative panel.

    just setup      # install everything
    just test       # run tests
    just gui        # open the launcher
    uv run staff list  # list tools from the CLI
    uv run staff library index && uv run staff library search while

The launcher has two sidebar roots: **Tools** (plugins) and **Resources**
(the Resource Library: search, preview and tag the teaching resources
folder; Office files open externally and are never parsed).

`just install` puts a thin launcher in /Applications that runs this checkout;
`staff update` (or Settings › Update now) pulls the latest code. Shortcuts: ⌘K
library search, ⌘O open for class, ⌘1–9 tools, ⌘L log, ⌘, settings.

Documentation: https://colepoppleton.github.io/Teaching-Tools/ (built from
`docs/` by MkDocs). MIT licensed.

See `CLAUDE.md` for the conventions and `docs/adding-a-tool.md` for how to add
a tool.
