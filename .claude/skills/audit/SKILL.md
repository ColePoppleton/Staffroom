---
name: audit
description: Deep product audit of Staffroom. Drives the actual app as several teacher personas, writes evidence-backed findings, then holds the PM / stakeholder meeting and turns the decisions into a GitHub Milestone of issues plus an explicit "not doing" list. Run from the main chat at the start of a phase, or when the user asks to audit, review the product, or plan the next phase.
---

# /audit

You are two things in sequence: first the **users**, then the **PM meeting**. Keep them
separate. Users produce evidence; the meeting produces decisions.

## 0. Ground yourself (read, do not skip)

1. `docs/ROADMAP.md` (the brief and hard rules), `docs/PHASES.md`, `CLAUDE.md`, `CHANGELOG.md`,
   `docs/process.md`, and the most recent file in `docs/audits/` if any.
2. The purpose, in one line you keep in front of you: *a UK secondary computing teacher's
   weekly workflow, on their own machine, outputs carried into school by hand, with no pupil
   data anywhere.* Everything is judged against that.
3. The current board: `gh issue list --state open --limit 200 --json number,title,labels,milestone`.
   You will reconcile with it, not pile on top of it.

## 1. Be the users (evidence, not opinion)

**Drive the product. Reading code is not an audit.** For every tool:

- Run its CLI on the example files in `examples/` and on at least one real-shaped input you make
  up (fake, marked `# FAKE DATA` if it is a table). Capture the exact command and output.
- Render its panel: `QT_QPA_PLATFORM=offscreen uv run staffroom --tool <name> [--open <file> --run] --screenshot <scratch>/<name>.png`
  in both themes. Look at every screenshot. Note anything unreadable, cramped, misleading,
  or that needs a manual the user does not have.
- Try to break it: empty input, a wrong file type, a huge file, a file with an identifier column,
  a program that loops forever, pasted code with tabs.

Walk four fixed personas through real tasks and write what they would actually say:

| Persona | Task | What they care about |
| --- | --- | --- |
| **The owner**, Sunday night, 40 minutes | Mark a mock, make a do-now for Monday, prep a Parsons problem | Speed, no re-entering things, outputs land where they expect |
| **A colleague**, first time, no instructions | Install it and get one worksheet out | What is unclear, what they cannot find, what they distrust |
| **A head of department** | "Where does pupil data go?" | Proof, not reassurance: what is stored, where, what is logged |
| **A trainee teacher**, weak Python | Trace tables and bugs for Year 9 | Jargon, defaults, whether the key is right |

Each finding is written as:
`[area] what happened → what the persona expected → evidence (command / screenshot / file) → severity (blocks / hurts / annoys / polish)`.

Also list what is **good** and must not be broken by any redesign. A phase that loses those
is a regression, whatever else it adds.

## 2. Be the PM meeting (decisions, with costs)

For each finding, and for each feature you believe is missing, decide with this table:

| Field | Rule |
| --- | --- |
| Value | Which persona, how often, how much time or risk it saves |
| Cost | S (under an hour) / M (a session) / L (several sessions; must be split) |
| Risk | What it could break; which hard rule it touches |
| Verdict | now / next / later / **not doing** (with the reason) |

Rules of the meeting:

- You **may** say "this design is wrong, start this part again". When you do, you must state the
  measurable failure it causes today, what the replacement is, what it breaks, and how we
  prove it is better. **At most one large redesign per phase.** A rewrite with no measured
  failure behind it is parked under `priority:later`, not scheduled.
- Anything that drifts from the purpose (features for pupils, cloud, accounts, anything that
  wants a class list) is rejected and recorded as rejected, so it is not re-proposed next time.
- Produce a **"not doing" list** as long as the "doing" list. A plan with no refusals is a wish list.
- The phase is about ten `priority:now` issues. Push the rest to `next` / `later`.

## 3. Write it down (the handoff; chat context will not survive)

1. `docs/audits/YYYY-MM-DD.md`: purpose check, what was run, persona findings with evidence,
   the good list, the decisions table, the not-doing list with reasons.
2. A Milestone for the phase: `gh api -X POST repos/{owner}/{repo}/milestones -f title="Phase N: <theme>" -f description="…"`.
3. One issue per decision using the task template in `.github/ISSUE_TEMPLATE/task.md`:
   `gh issue create --title "…" --body-file <tmp> --label status:ready --label "priority:now" --label "type:…" --label "size:…" --label audit --milestone "Phase N: …"`.
   Body **must** contain: *Why (user-facing)*, *Acceptance criteria* as a checklist, *Touches*
   (areas), and a link back to the audit file section.
4. Reconcile: close issues the product no longer needs (say why in a comment), re-prioritise
   stale ones, never create a duplicate of an open issue.
5. Finish with a one-screen summary in chat: the phase theme, the ten issues in order, the
   top three refusals and why, and the one redesign if there is one. Ask the user to veto
   before anything is picked up. Do not start implementing.

## What not to do

- Do not implement anything. Do not touch `dev` or `main`.
- Do not propose rewrites without evidence from section 1.
- Do not invent personas with pupil data. The HoD persona exists to check that none is held.
- Do not write findings from reading code alone; every finding cites something you ran.
