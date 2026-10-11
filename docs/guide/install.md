# Install

## The canonical way: `uv tool install` from GitHub

Staffroom is a Python package. Installing it as a tool gives you the
`staff` and `staffroom` commands without touching any other Python on the machine.
It is **not on PyPI**, so install it straight from the GitHub repository,
pinned to a release tag.

1. Install [uv](https://docs.astral.sh/uv/) if you don't have it:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. Install the tools (this is the latest release, v0.6.0):
   ```bash
   uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@v0.8.0
   ```
3. Start the launcher:
   ```bash
   staffroom
   ```

If the terminal says `staffroom: command not found`, run `uv tool update-shell`
and open a new terminal window: uv puts the commands in `~/.local/bin`, which
is not always on the path yet.

`--python 3.12` makes uv use (and if needed download) a Python that Staffroom
supports; without it uv may pick an older Python already on the Mac and stop
with "the current Python version does not satisfy Python>=3.12".

!!! warning "The repository is private for now"
    The line above only works for someone who can see
    [github.com/ColePoppleton/Staffroom](https://github.com/ColePoppleton/Staffroom).
    uv asks git for the code, so git needs your GitHub sign-in (the macOS
    keychain or `gh auth login` handles this). A colleague without access gets
    a "repository not found" or sign-in error, and so would the wheel attached
    to the [GitHub Release](https://github.com/ColePoppleton/Staffroom/releases).
    Until the repository is public, ask the owner to add you, or to send you
    the `.whl` file from the latest release and install that with
    `uv tool install --python 3.12 ./staffroom-0.8.0-py3-none-any.whl`.

!!! note "Why not `uv tool install` with just the name?"
    There is no Staffroom package on PyPI, and the name is not reserved, so
    installing by name would fail today, or install a stranger's package if
    someone registers it. The short form will appear here only once Staffroom
    is published there.

To upgrade, run the same line with the newer tag from the
[Releases](https://github.com/ColePoppleton/Staffroom/releases) page; see
[Updating](updating.md).

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
git clone https://github.com/ColePoppleton/Staffroom
cd Staffroom
just setup      # uv sync + pre-commit hooks
just test
just gui
```
