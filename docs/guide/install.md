# Install

## The canonical way: `uv tool install`

Teaching Tools is a Python package. Installing it as a tool gives you the
`tt` and `tt-gui` commands without touching any other Python on the machine.

1. Install [uv](https://docs.astral.sh/uv/) if you don't have it:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. Install the tools:
   ```bash
   uv tool install teaching-tools
   ```
3. Start the launcher:
   ```bash
   tt-gui
   ```

Upgrade later with `uv tool upgrade teaching-tools`.

!!! note "Until the first PyPI release"
    Install straight from GitHub:
    `uv tool install git+https://github.com/ColePoppleton/Teaching-Tools`.
    Add `@v0.2.0` (any tag) to pin a version.

## macOS: a Dock icon

If you work from a git checkout, `just install` builds a tiny launcher app
and copies it to /Applications. It runs the checkout with uv, so a code
update needs no reinstall. See [Updating](updating.md).

## Windows and Linux

The code is Python and Qt, so it runs, but the editor commands, file
opening and the sandbox limits are tuned for macOS today. Expect rough edges;
they are on the roadmap, not a priority yet.

## For developers

```bash
git clone https://github.com/ColePoppleton/Teaching-Tools
cd Teaching-Tools
just setup      # uv sync + pre-commit hooks
just test
just gui
```
