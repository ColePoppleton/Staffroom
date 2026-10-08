# Updating

## Installed with `uv tool install`

```bash
uv tool upgrade staffroom
```

## Running from a checkout (the macOS launcher app)

The app checks the git remote when it starts and compares your checkout with
the **released branch**, `origin/main`, whatever branch you happen to be on.
If a release is ahead, **Update available** appears in the sidebar; Settings ›
Updates has *Check for updates* and *Update now*, and the status line names
the newest release tag (for example `v0.5.0`). Restart afterwards.

From the terminal the same thing is `staff update` (or `staff update --check` to
only look). It fast-forwards `main` and syncs dependencies. It never switches
branch, never overwrites local edits and never merges a diverged branch; it
tells you instead:

| Status line says | Meaning |
| --- | --- |
| `Up to date with origin/main (abc1234)` | Nothing to do. |
| `2 updates available (abc1234 → origin/main, v0.5.0)` | *Update now* fast-forwards. |
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
