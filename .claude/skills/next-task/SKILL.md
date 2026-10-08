---
name: next-task
description: Pick up the next ready issue from the GitHub Issues board, claim it so parallel sessions do not overlap, work it in its own git worktree on a feature branch from dev, and open a pull request to dev. Run from a fresh chat; also when the user says "next task", "pick up the next ticket", or names an issue number to work on.
---

# /next-task

One issue, one branch, one PR. Never work in the main checkout.

## 1. Pick

1. `gh issue list --label status:ready --state open --limit 50 --json number,title,labels,body,milestone`.
2. Prefer, in order: the user named an issue → `priority:now` in the current milestone →
   smallest size → oldest. Skip `status:blocked`.
3. **Avoid overlap:** read the *Touches* section of every `status:in-progress` issue
   (`gh issue list --label status:in-progress --json number,body`). Skip a candidate whose
   areas overlap one in progress; say which one blocked it.
4. If nothing is ready, say so and stop. Do not invent work.

## 2. Claim (optimistic lock)

```
branch=feat/<number>-<short-slug>      # fix/ for type:bug, chore/ or docs/ likewise
gh issue edit <n> --add-label status:in-progress --remove-label status:ready
gh issue comment <n> --body "Claimed: branch \`$branch\`, $(date -u +%Y-%m-%dT%H:%MZ), $(hostname -s)"
```

Then re-read the comments. If another *Claimed:* comment is older than yours, remove your
label change, apologise in a comment, and go back to step 1. Good enough for a handful of
concurrent sessions.

## 3. Worktree, never checkout

```
git fetch origin
git worktree add ../Teaching-Tools-worktrees/$branch -b $branch origin/dev
cd ../Teaching-Tools-worktrees/$branch && uv sync
```

Everything from here happens in that folder. The main checkout stays on whatever branch the
user left it on. Do not `git checkout` there.

## 4. Work

- Read `CLAUDE.md` and the issue's acceptance criteria before touching code. The hard rules are
  not negotiable: no pupil data, tools never import Qt, logic never does I/O, new UI goes into
  the shared widget kit.
- Write the test first when the criterion is testable; it usually is.
- Keep to the issue. Anything else you notice becomes a new issue:
  `gh issue create --title "…" --body "…" --label status:ready --label priority:next` and a
  one-line mention in the PR.
- Add a line under `## [Unreleased]` in `CHANGELOG.md`.
- If the UI changed, take a screenshot:
  `QT_QPA_PLATFORM=offscreen uv run tt-gui --tool <name> --screenshot <path> …`.
- `just check` must be green before a PR. Fix what it finds; do not weaken the checks.
- Commit in small steps with messages that say *why*. End the message with
  `Co-Authored-By: Claude <noreply@anthropic.com>`.

## 5. Pull request

```
git push -u origin $branch
gh pr create --base dev --title "<type>: <what> (#<n>)" --body-file <filled template>
gh issue edit <n> --add-label status:review --remove-label status:in-progress
```

Fill `.github/pull_request_template.md` honestly: tick only what is true. Attach the screenshot.
State anything unfinished and why. Do not merge; `/merge-prs` does that from the main chat.

## 6. If you get stuck

Label the issue `status:blocked`, write a comment that says exactly what decision or input is
needed, push what you have as a draft PR (`gh pr create --draft`), and stop. A clear blocked
note is a good outcome; a guessed design is not.

## Never

- Never work in the main checkout or on `dev` / `main` directly.
- Never resolve a merge conflict with `dev` by discarding the other side; rebase and reason.
- Never add data files with names, classes or anything that looks like a pupil.
