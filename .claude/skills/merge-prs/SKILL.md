---
name: merge-prs
description: Release-manager pass from the main chat. Reviews every open pull request against its issue's acceptance criteria and CI, merges the green ones into dev, sends the rest back with precise comments, cuts a dev → main release when a milestone is done, back-merges hotfixes, and cleans up branches, worktrees and labels. Run when the user says merge, review the PRs, release, or tidy the board.
---

# /merge-prs

You are the release manager. Nothing merges unseen; nothing rots on the board.

## 1. Survey

```
gh pr list --state open --json number,title,headRefName,baseRefName,isDraft,statusCheckRollup,mergeable,body,labels
gh issue list --label status:review --json number,title
```

For each PR, find its issue (`Closes #n` in the body) and read the acceptance criteria.

## 2. Review each PR, in this order

1. **CI.** Must be green. If pending, run the checks locally on the branch in a worktree
   (`git worktree add ../Teaching-Tools-worktrees/review-<n> origin/<branch>`, `uv sync`,
   `just check`). Never merge red.
2. **Criteria.** Tick each acceptance criterion against the diff and the tests. A criterion
   with no test needs a reason in the PR.
3. **Hard rules.** `tests/test_boundaries.py` and `lint-imports` pass; nothing that looks like
   pupil data was added; UI changes went into the widget kit, not a tool.
4. **Changelog line present**, screenshot present if UI changed.
5. **Read the diff as a reviewer**, not a linter: naming, duplication, anything the next
   session will trip over. Small nits are fine to fix yourself on the branch; design
   problems go back as comments.

Verdict per PR: **merge**, **changes requested** (comment on the PR with exact asks, label the
issue `status:in-progress`, mention it is back on the board), or **blocked** (label
`status:blocked`, say what decision is needed).

## 3. Merge

Default is to **present the verdicts and ask** before merging. If the user has said
"merge everything green" for this run, proceed without asking.

```
gh pr merge <n> --squash --delete-branch
gh issue close <issue> --comment "Merged in #<pr>"
```

Merge in dependency order; rebase later PRs onto the updated `dev` if they conflict
(`git rebase origin/dev` in the review worktree, push, re-run checks). A conflict that needs
product judgement goes back to the author session as `status:blocked`, not resolved by guesswork.

## 4. Release (dev → main) when a milestone is done or the user asks

1. `git fetch`, confirm `dev` CI is green.
2. Open `gh pr create --base main --head dev --title "Release vX.Y.Z"` with the Unreleased
   changelog as body; merge it with a **merge commit** (`gh pr merge --merge`).
3. On `main`: `just release <patch|minor|major>` (bumps, moves Unreleased, commits, tags,
   pushes). The tag triggers the Release workflow; check it succeeded
   (`gh run list --workflow release.yml --limit 1`).
4. Close the milestone. Announce the version and the one-line highlights in chat.
5. Merge `main` back into `dev` so the version bump is not lost.

**Hotfix:** branch `hotfix/X.Y.Z` from the `main` tag, fix with a test, PR to `main`, release as
above, then merge `main` into `dev`. Never hotfix on `dev` and cherry-pick by hand.

## 5. Clean up every run

- `git worktree prune`; remove review worktrees you created.
- Delete merged remote branches that `--delete-branch` missed (`gh api` or `git push origin --delete`).
- Any `status:in-progress` issue with no claim activity for 7 days: comment, revert to
  `status:ready`, remove the stale claim.
- Any `status:review` issue with no open PR: revert to `status:ready`.
- Report: merged, sent back, blocked, released, cleaned.

## Never

- Never merge a red or unreviewed PR, even your own session's.
- Never force-push `dev` or `main`; never rewrite tags.
- Never resolve a conflict by taking one side wholesale.
