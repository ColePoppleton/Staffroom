# Teaching Tools

A CurseForge-style launcher for small Python tools used by a UK secondary
computing teacher. One desktop shell (PySide6) lists installed tools in a
sidebar; each tool is a plugin that owns its logic and a declarative panel.

    just setup      # install everything
    just test       # run tests
    just gui        # open the launcher
    uv run tt list  # list tools from the CLI

See `CLAUDE.md` for the conventions and `docs/adding-a-tool.md` for how to add
a tool.
