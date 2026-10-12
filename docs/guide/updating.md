# Updating

## Installed with `uv tool install`

Quit Staffroom, then run this in Terminal and open Staffroom again:

```bash
uv tool upgrade staffroom
```

The install line follows `main`, the branch that only ever holds released
versions, so this one command moves you to the newest release. Staffroom
never updates itself and never runs git; it tells you when there is
something to update:

- **Settings › Updates** shows *This copy* (the version you are running),
  the *Newest release* with its date and *What changed ▸* (the release
  notes, and a link to the release on GitHub), and the command above with a
  *Copy* button. *Check again* asks GitHub straight away.
- **The foot of the sidebar** adds the newer release's number and *out*
  beside your version while a newer release is out; click it to open
  Settings › Updates.

To learn about a release, Staffroom asks GitHub's public Releases API which
release is newest: when you press *Check again*, and at most once a day when
it opens while *Look for a new release when Staffroom opens* is ticked (it
is by default; untick it to stop). Nothing about you or your files is sent;
the [Privacy](privacy.md#where-things-live) page has the details. If GitHub
cannot be reached (no network, a school filter), the card says so in one
sentence and never claims you are up to date; the command still works
whenever you can reach GitHub.

!!! note "Installed from a release tag or a `.whl` file?"
    Copies installed with a line ending in `@v` and a version number (an
    older install line), or from a `.whl` file, are pinned: `uv tool upgrade staffroom` answers *Nothing to
    upgrade*. Run the install line once more and later updates are the one
    command above. Settings › Updates shows this line for a pinned copy.

    ```bash
    uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@main
    ```

## Which version am I running?

The foot of the sidebar shows it: `v` and the version number, followed by
*· up to date* once the app has checked for a release (just the version
before it has, and when it cannot check).

![The sidebar footer with the version, dark theme](../sidebar-footer-dark.png)
![The sidebar footer with the version, light theme](../sidebar-footer-light.png)

Settings › Updates says the same: *This copy* for an installed copy; in a
checkout, the top line of the card. On a release tag it is just the version
(`Running Staffroom X.Y.Z`); anywhere else it adds the branch and the short
commit (`Running Staffroom X.Y.Z (dev, a1b2c3d)`), which
is what to quote when reporting a problem. From the terminal:
`staffroom --version` or `staff version`.

The launcher app's Get Info in Finder shows the version it was built from.
`just install` rebuilds it; an update through the app or `staff update` does
not, so Get Info can lag behind the sidebar until the next `just install`.

## Running from a checkout (the macOS launcher app)

The app checks the git remote when it starts and compares your checkout with
the **released branch**, `origin/main`, whatever branch you happen to be on.
If a release is ahead, an **update** link appears beside the version at the
foot of the sidebar and opens Settings › Updates; Settings ›
Updates has *Check for updates* and *Update now*, and the status line names
the newest release tag (`vX.Y.Z`). Restart afterwards.

From the terminal the same thing is `staff update` (or `staff update --check` to
only look). It fast-forwards `main` and syncs dependencies. It never switches
branch, never overwrites local edits and never merges a diverged branch; it
tells you instead:

| Status line says | Meaning |
| --- | --- |
| `Up to date with origin/main (abc1234)` | Nothing to do. |
| `2 updates available (abc1234 → origin/main, vX.Y.Z)` | *Update now* fast-forwards. |
| `…; on dev; releases are on main` | The checkout is on another branch. The release is reported but not pulled; switch to `main` yourself if you want it. |
| `…; main has no upstream; comparing with origin/main` | The branch has no tracking ref. Harmless: the release branch is still compared and can be pulled. |
| `…; detached (not on a branch); releases are on main` | Detached HEAD. Reported, never pulled. |
| `abc1234 on main; no remote configured` | Nothing to compare with. |
| `Could not check: origin has no 'main' branch to update from` | The remote has no release branch of that name. |

If you release from a different branch, set it in `config.toml`:

```toml
[general]
release_branch = "main"
```

## Versions

Releases follow semantic versioning and are tagged `vX.Y.Z` on `main`; each
one is a GitHub Release with the changelog section as its notes. The full
history is in the [changelog](../changelog.md).
