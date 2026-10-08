# Updating

## Installed with `uv tool install`

```bash
uv tool upgrade staffroom
```

## Running from a checkout (the macOS launcher app)

The app checks the git remote when it starts. If a newer version is on the
`main` branch, **Update available** appears in the sidebar; Settings › Updates
has *Check for updates* and *Update now*. Restart afterwards.

From the terminal the same thing is `staff update` (or `staff update --check` to
only look). It fast-forwards and syncs dependencies; it never overwrites
local edits or a diverged branch, it tells you instead.

## Versions

Releases follow semantic versioning and are tagged `vX.Y.Z` on `main`; each
one is a GitHub Release with the changelog section as its notes. The full
history is in the [changelog](../changelog.md).
