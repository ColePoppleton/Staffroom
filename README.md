# Teaching Tools

A CurseForge-style launcher for small Python tools used by a UK secondary
computing teacher. One desktop shell (PySide6) lists installed tools in a
sidebar; each tool is a plugin that owns its logic and a declarative panel.

    just setup      # install everything
    just test       # run tests
    just gui        # open the launcher
    uv run tt list  # list tools from the CLI
    uv run tt library index && uv run tt library search while

The launcher has two sidebar roots: **Tools** (plugins) and **Resources**
(the Resource Library: search, preview and tag the teaching resources
folder; Office files open externally and are never parsed).

`just app` builds `dist/Teaching Tools.app` for the Dock. Shortcuts: ⌘K
library search, ⌘O open for class, ⌘1–9 tools, ⌘L log, ⌘, settings.

See `CLAUDE.md` for the conventions and `docs/adding-a-tool.md` for how to add
a tool.
