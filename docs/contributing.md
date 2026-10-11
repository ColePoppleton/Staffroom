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

```bash
git clone https://github.com/ColePoppleton/Staffroom
cd Staffroom
just setup
just gui
```

`just` lists the other commands: `just test`, `just lint`, `just check` (both,
as CI runs them), `just screenshots`, `just docs`.

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
2. Branch from `dev`: `feat/<issue>-<slug>`, `fix/…`, `docs/…` or `chore/…`.
3. Add tests with the change and run `just check` until it is green.
4. Add a line under `## [Unreleased]` in `CHANGELOG.md`.
5. If the screen changed, include before and after screenshots in the pull
   request. `just screenshots` renders the docs images offscreen from invented
   fixture data, never from a real home folder.
6. Open a pull request to `dev`. It is squash-merged once CI is green.

Releases are a pull request from `dev` to `main` followed by a `vX.Y.Z` tag;
the tag builds the GitHub Release.

## Adding a tool

See [Adding a tool](adding-a-tool.md). The `hello` tool is the reference
example, and `just new <name>` scaffolds a working one.
