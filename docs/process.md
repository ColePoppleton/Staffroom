# How work flows

One repo, two long-lived branches, three skills, GitHub Issues as the board.

## Branches

| Branch | Purpose | Protected |
| --- | --- | --- |
| `main` | Released. The installed app tracks it. Tags `vX.Y.Z` live here. | PR + green CI |
| `dev` | Integration. Feature PRs land here continuously. | PR + green CI |
| `feat/<issue>-<slug>`, `fix/…`, `chore/…`, `docs/…` | One issue each, branched from `dev`. | no |
| `hotfix/<version>` | Branched from a `main` tag; merged to `main`, tagged, then `main` merged back into `dev`. | no |

Feature PRs target `dev` and are **squash-merged** (one commit per issue). Releases are a PR
`dev → main` with a **merge commit**, then a tag. Every task session works in its own
`git worktree` so parallel sessions never share a checkout or a `.venv`.

## The board (GitHub Issues)

| Label | Meaning |
| --- | --- |
| `status:ready` | Can be picked up now |
| `status:in-progress` | Claimed: the issue has a claim comment with the branch name |
| `status:review` | PR open |
| `status:blocked` | Needs a decision or external input |
| `priority:now / next / later` | This phase / next phase / someday |
| `type:feature / redesign / bug / docs / chore` | Kind of work |
| `size:S / M / L` | Under an hour / a session / several (split it) |
| `audit` | Raised by an audit run |

A **Milestone** is a phase. An issue must have: a user-facing *why*, acceptance criteria as a
checklist, the areas it touches (`core/export`, `tools/marks`, …), a size and a priority.

## The skills

| Skill | Where | What |
| --- | --- | --- |
| `/audit` | main chat | Drives the product as several personas, reviews every section's layout and flow with mockups, then holds the PM meeting: a milestone of issues (redesigns where the design pass justifies them, each shown as a mockup) plus a "not doing" list. |
| `/next-task` | a new chat | Claims the best `status:ready` issue, works it in a worktree on a feature branch, opens a PR to `dev`. |
| `/merge-prs` | main chat | Reviews open PRs against their issues, merges green ones, releases `dev → main`, cleans up. |

## Definition of done (every PR)

- Tests for the change; `just check` green locally; CI green.
- A line under `## [Unreleased]` in `CHANGELOG.md`.
- A screenshot in the PR if the UI changed. If a docs screenshot is affected, `just screenshots`
  regenerates the whole set offscreen (`scripts/screenshots.sh`; never from the owner's real home).
  `scripts/screenshots.sh outputs` redoes only the rendered pages. The script sets
  `STAFFROOM_DATE=YYYY-MM-DD`, which every exported sheet prints in its header instead of today's
  date, so the renders are the same bytes on any day; leave it unset for real use.
- The hard rules in `CLAUDE.md` still hold (no pupil data; tools never import Qt; logic never does I/O).
- Anything noticed but out of scope became a new issue, not a bigger PR.
