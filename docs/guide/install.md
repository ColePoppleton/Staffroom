# Install

## The canonical way: `uv tool install` from GitHub

Staffroom is a Python package. Installing it as a tool gives you the
`staff` and `staffroom` commands without touching any other Python on the machine.
It is **not on PyPI**, so install it straight from the GitHub repository's
`main` branch, which only ever holds released versions.

1. Install [uv](https://docs.astral.sh/uv/) if you don't have it:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   Then **open a new Terminal window** (or run `source $HOME/.local/bin/env`).
   uv's installer adds itself only to windows opened after it, so step 2 in
   the same window stops with `uv: command not found`.
2. In the new window, install Staffroom (the newest release):
   ```bash
   uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@main
   ```
3. Start the launcher:
   ```bash
   staffroom
   ```

If the terminal says `uv: command not found`, open a new Terminal window: uv
was installed in step 1 but this window does not know yet. If it says
`staffroom: command not found`, run `uv tool update-shell` and open a new
Terminal window: uv puts the commands in `~/.local/bin`, which is not always
on the path yet.

`--python 3.12` makes uv use (and if needed download) a Python that Staffroom
supports; without it uv may pick an older Python already on the Mac and stop
with "the current Python version does not satisfy Python>=3.12".

The install takes about 500 MB of disk, most of it Qt: Staffroom installs only
the parts of Qt it uses (PySide6-Essentials and PySide6-Pdf, no web engine).
It needs macOS 14 Sonoma or later, which that Qt release is built for.

!!! note "No account needed"
    The repository is public, so the line above works on any Mac with uv and
    git; no GitHub sign-in is needed. If git is missing, or a school network
    blocks it, download the `.whl` file from the latest
    [GitHub Release](https://github.com/ColePoppleton/Staffroom/releases) and
    install that instead:
    `uv tool install --python 3.12 ./staffroom-0.8.1-py3-none-any.whl`.

!!! note "Why not `uv tool install` with just the name?"
    There is no Staffroom package on PyPI, and the name is not reserved, so
    installing by name would fail today, or install a stranger's package if
    someone registers it. The short form will appear here only once Staffroom
    is published there.

To update later, quit Staffroom and run `uv tool upgrade staffroom`.
Settings › Updates says when a new release is out and shows the same
command with a *Copy* button; see [Updating](updating.md).

## macOS: a Dock icon

If you work from a git checkout, `just install` builds a tiny launcher app
and copies it to /Applications. It runs the checkout with uv, so a code
update needs no reinstall. See [Updating](updating.md).

## Windows and Linux

The code is Python and Qt, so it runs, but the editor commands, file
opening and the sandbox limits are tuned for macOS today. Expect rough edges;
they are on the roadmap, not a priority yet.

## For developers

To change the code, fork the repository and work from a clone of your fork:
[How to contribute](../contributing.md) has the setup, and how to try a
change in throwaway folders without touching your own Staffroom.
