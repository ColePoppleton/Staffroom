# Contributing

Staffroom is open source under the MIT licence. Bug reports, fixes and new tools
are welcome. This page covers setting up, the rules every change keeps, and how
a change gets in.

## Report a problem or suggest an idea

Choose a form on
[New issue](https://github.com/ColePoppleton/Staffroom/issues/new/choose):
**Bug report** when something went wrong, **Idea for a tool or change** for
anything new. Plain words are fine. The issue tracker is public, so attach
nothing from school: no marks files, markbook exports, class lists or
screenshots with names. Make a small invented example instead, starting from
the [example files](https://github.com/ColePoppleton/Staffroom/tree/main/examples).

A new report is labelled `status:triage`; a maintainer reads it and turns it
into work on the board. If you have found a privacy problem (Staffroom kept,
showed or logged something it should not have), report it privately instead,
as [SECURITY.md](https://github.com/ColePoppleton/Staffroom/blob/main/.github/SECURITY.md)
describes.

## Set up

You need macOS, [uv](https://docs.astral.sh/uv/) and
[just](https://github.com/casey/just).

Fork first: press **Fork** on
[the repository](https://github.com/ColePoppleton/Staffroom), then clone your
fork, not the original. Your branches and pull requests come from there.

```bash
git clone https://github.com/<your-name>/Staffroom
cd Staffroom
git remote add upstream https://github.com/ColePoppleton/Staffroom
just setup
```

`just` lists the other commands: `just test`, `just lint`, `just check` (both,
as CI runs them), `just screenshots`, `just docs`. `just check` runs the whole
suite, the Qt shell offscreen included: allow about three minutes on a recent
Mac, longer the first time.

### Try it without touching your own Staffroom

`just gui` and `just run` use the same folders as an installed Staffroom:
your settings and library index in `~/.config/staffroom`, lesson copies and
outputs in `~/TeachingSessions`. If you teach with Staffroom too, try changes
in throwaway folders instead. Two environment variables redirect them:

```bash
export STAFFROOM_HOME="$(mktemp -d)" STAFFROOM_SESSIONS="$(mktemp -d)"
just gui
just run hello run examples/marks_10x.csv   # writes to $STAFFROOM_SESSIONS/outputs/hello
```

`STAFFROOM_HOME` replaces the settings folder; `STAFFROOM_SESSIONS` replaces
the default sessions folder (a sessions folder chosen in Settings still wins).
They last until you close the terminal. The tests set both for every test, and
`just screenshots` does the same, so neither ever reaches your real folders.

## The rules every change keeps

- **No pupil data, ever.** No class lists, names, candidate numbers or anything
  per pupil goes in or comes out. Tables are read through `core.csvio`, which
  drops identifier columns before a tool sees them; a test fails the build if a
  tool reads a CSV or spreadsheet any other way. Example and test data are
  invented, marked `# FAKE DATA`, and contain no names.
- **Tools never import Qt.** A tool describes its screen with the panel
  vocabulary in `core/panel.py`; the shell draws it. A new kind of widget goes
  into the shared widget kit so every tool can use it.
- **Logic never does I/O.** `tools/<name>/logic.py` is pure functions; reading
  and writing files happens in the plugin or the CLI.
- **The resources folder is read-only.** Edits happen on lesson copies; tags
  live in a sidecar file.
- **Pupil code runs only through `core/runner`**, never with `exec`.

`just check` enforces the import rules and runs the boundary tests.

## How a change gets in

1. Open an issue with one of the forms above, or comment on an existing one,
   so work is not duplicated.
2. In your fork, branch from `dev` (`git fetch upstream` and branch from
   `upstream/dev`): `feat/<issue>-<slug>`, `fix/…`, `docs/…` or `chore/…`.
3. Add tests with the change and run `just check` until it is green (about
   three minutes).
4. Add a line under `## [Unreleased]` in `CHANGELOG.md`.
5. If the screen changed, include before and after screenshots in the pull
   request. `just screenshots` renders the docs images offscreen from invented
   fixture data, never from a real home folder.
6. Push the branch to your fork and open a pull request to `dev` on
   ColePoppleton/Staffroom. It is squash-merged once CI is green.

Releases are a pull request from `dev` to `main` followed by a `vX.Y.Z` tag;
the tag builds the GitHub Release.

## Adding a tool

See [Adding a tool](adding-a-tool.md). The `hello` tool is the reference
example, and `just new <name>` scaffolds a working one like it. `staff new`
only works in a clone: from an installed copy it says so and writes nothing.

## Where to ask

On GitHub, in the open. Ask on the issue you are working on; if there is no
issue yet, open one with the **Idea for a tool or change** form and say it is a
question. There is no chat or forum. A privacy problem goes privately, as
[SECURITY.md](https://github.com/ColePoppleton/Staffroom/blob/main/.github/SECURITY.md)
describes.
