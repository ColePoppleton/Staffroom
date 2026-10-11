---
name: audit
description: Deep product audit of Staffroom. Drives the actual app as several teacher personas, writes evidence-backed findings, then holds the PM / stakeholder meeting and turns the decisions into a GitHub Milestone of issues plus an explicit "not doing" list. Run from the main chat at the start of a phase, or when the user asks to audit, review the product, or plan the next phase.
---

# /audit

You are two things in sequence: first the **users**, then the **PM meeting**. Keep them
separate. Users produce evidence; the meeting produces decisions.

## 0. Ground yourself (read, do not skip)

1. `docs/ROADMAP.md` (the brief and hard rules), `docs/PHASES.md`, `CLAUDE.md`, `CHANGELOG.md`,
   `.claude/process.md`, and the most recent file in `docs/audits/` if any.
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

## 1b. Be the designer (structure, layout, flow)

Bugs are not the only failures. A screen that works but is laid out badly costs the teacher
time every week, and a bug hunt will never find it. Do this pass separately from section 1,
after it, with fresh eyes on the screenshots.

For **every section of the app** (sidebar and navigation, each tool panel, the run bar and
results area, the Resource Library, Settings, first run, the docs site's landing page) answer
in writing, with the screenshot beside you:

- **Task flow.** What does the teacher come here to do, step by step? Count the clicks, the
  scrolling and the fields they must read before the first useful output. Where do they stop
  and wonder?
- **Hierarchy.** What does the eye land on first? Is that the most important thing? Is the
  primary action obvious, or is it one button among many?
- **Structure.** Is this section organised around how a teacher thinks (a lesson, a class
  sitting, a mock) or around how the code happens to be split (one form field per dataclass
  attribute, one card per widget type)? Would a teacher group these things differently?
- **Density and space.** What is wasted (empty canvas, a log nobody reads taking a third of
  the panel)? What is cramped or clipped?
- **Consistency.** Do sibling tools put the same things in the same places? Does the same
  idea look the same everywhere?
- **What a good product would do.** Name one or two well-made apps a teacher already uses and
  how they solve the same problem. Steal shamelessly.

Where the pass shows a real cost, propose a redesign of that section and **show it**: a rendered
mockup (an HTML file or an offscreen Qt prototype rendered to PNG, saved under `data/audit/`)
next to the current screenshot, what moves where, what is removed, what the teacher saves
(clicks, scrolling, time, mistakes), and what it puts at risk. When a section does need it,
prefer a bold, coherent proposal over a list of nudges: "put the results beside the inputs and
drop the log card behind a toggle" beats "make the log 20% shorter". There is no quota: a
section that is genuinely fine says so, with the reason, and gets no redesign.

The evidence for a design finding is the screenshot, the step count and the comparison; it
does not need a crash or a wrong number behind it.

## 2. Be the PM meeting (decisions, with costs)

For each finding, and for each feature you believe is missing, decide with this table:

| Field | Rule |
| --- | --- |
| Value | Which persona, how often, how much time or risk it saves |
| Cost | S (under an hour) / M (a session) / L (several sessions; must be split) |
| Risk | What it could break; which hard rule it touches |
| Verdict | now / next / later / **not doing** (with the reason) |

Rules of the meeting:

- You **should** say "this design is wrong, start this part again" whenever section 1b shows it.
  State the failure it causes today (a bug, or a design cost from 1b: steps, scrolling, hidden
  primary action, wasted space, inconsistency), the replacement (with the mockup), what it
  breaks, and how we will know it is better (step counts, before/after screenshots, a page
  count, a test). There is **no cap and no quota**: schedule as many redesigns as the design pass
  justifies, none if it justifies none. A redesign covers a whole section where that is what is
  wrong, not just a widget. Large ones are split into issues that each leave the app working,
  but the split must not shrink the ambition.
- Redesigns may change the shared widget kit, the panel vocabulary (`core/panel.py`) and the
  shell's layout wholesale. The engineering rules still hold: tools describe UI through the
  vocabulary, never Qt; new UI lives in the kit so every tool benefits.
- Anything that drifts from the purpose (features for pupils, cloud, accounts, anything that
  wants a class list) is rejected and recorded as rejected, so it is not re-proposed next time.
- Produce a **"not doing" list**. A plan with no refusals is a wish list, but do not pad it,
  and do not use it to park a redesign that section 1b argued for.
- The phase is about ten `priority:now` issues. Push the rest to `next` / `later`.

## 3. Write it down (the handoff; chat context will not survive)

1. `docs/audits/YYYY-MM-DD.md`: purpose check, what was run, persona findings with evidence,
   the good list, the decisions table, the not-doing list with reasons.
2. A Milestone for the phase: `gh api -X POST repos/{owner}/{repo}/milestones -f title="Phase N: <theme>" -f description="…"`.
3. One issue per decision using the task template in `.github/ISSUE_TEMPLATE/task.md`.
   A `type:redesign` issue also carries the mockup (committed under `docs/audits/<date>/`),
   the target layout in words, and an explicit line: *"This issue expects structural change;
   rewriting the section's layout and the widgets it uses is in scope."*
   `gh issue create --title "…" --body-file <tmp> --label status:ready --label "priority:now" --label "type:…" --label "size:…" --label audit --milestone "Phase N: …"`.
   Body **must** contain: *Why (user-facing)*, *Acceptance criteria* as a checklist, *Touches*
   (areas), and a link back to the audit file section.
4. Reconcile: close issues the product no longer needs (say why in a comment), re-prioritise
   stale ones, never create a duplicate of an open issue.
5. Finish with a one-screen summary in chat: the phase theme, the ten issues in order, the
   top three refusals and why, and every redesign with a link to its mockup. Ask the user to veto
   before anything is picked up. Do not start implementing.

## What not to do

- Do not implement anything. Do not touch `dev` or `main`.
- Do not propose rewrites without evidence from section 1 or 1b.
- Do not skip section 1b. If it finds nothing worth redesigning, say so section by section
  with the reason; do not invent a redesign to fill a slot.
- Do not invent personas with pupil data. The HoD persona exists to check that none is held.
- Do not write findings from reading code alone; every finding cites something you ran.
