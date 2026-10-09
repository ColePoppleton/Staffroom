# Glossary

The words the panels and the sheets use without explaining them. Where a
term has a precise meaning in the code, this is that meaning.

## Assessment

**Facility (index)**
: For one question, the mean mark across the scripts divided by the
  question's maximum, so a number from 0 to 1. A facility of 0.35 means the
  class scored 35% of the available marks on it. Low facility is the
  *reteach* signal; Marks lists the worst questions by it. Blank or
  non-numeric cells are left out of the mean.

**Discrimination**
: For one question, how well it separates the stronger scripts from the
  weaker ones: scripts are ranked by total mark, and the question's mean in
  the top third minus its mean in the bottom third is divided by its
  maximum. Near 1 means the strongest scripts got it and the weakest did
  not; near 0 means everyone did about the same (too easy, too hard, or
  luck); negative means the weaker scripts did better, which usually means
  a flawed question or a mark-scheme slip.

**MAX row**
: In a marks file, the row that holds the maximum mark for each question.
  It is found by the word `MAX` in any cell and never counted as a script.
  See [Marks files](marks-files.md).

**Incomplete scripts**
: Scripts (rows) with at least one blank or non-numeric cell in a question
  column. The cell counts as 0 in the script's total and grade, is left out
  of facility and discrimination, and the distribution table gets a last
  row saying how many scripts were affected. The chart leaves that row out.

**Boundary, preset**
: A grade and the minimum needed for it, as a percentage of the paper or
  as raw marks (*Boundary unit*). A preset is a saved table of boundaries;
  the built-in ones are starting points, not the published figures.

**Identifier column**
: A column whose header names a pupil or a group (`Name`, `Candidate
  Number`, `Class`…). Dropped on load by every tool, with no way to turn
  that off. The full word list, and what it does not catch, is in
  [Privacy](privacy.md).

## Sheets

**Seed**
: The whole number that fixes every random choice a generator makes. The
  same seed with the same settings produces the same sheet, so the seed is
  printed on the sheet and put in its file name (`_s42`). Change it for a
  different set; keep it to reprint a lost one.

**Key**
: The answer version of a sheet. It is written as a separate file with
  `_key` added to the name, so it cannot be printed by accident with the
  pupil copy. See [Outputs](outputs.md).

**House style**
: The one look every sheet shares: your header and footer text, the title,
  topic and date, numbered questions, monospace code. Set in Settings; see
  [House style](house-style.md).

**Parsons problem**
: A working program cut into blocks and shuffled; pupils put the blocks
  back in order (and, with *Show indentation* off, decide the indents). The
  key is the original program.

**Distractor**
: A block that does not belong: a real line with its colon removed, a
  comparison flipped or a number off by one. In Quiz, a wrong option in a
  multiple-choice question.

**Trace table**
: One row per executed line of a program, showing every chosen variable's
  value *after* that line ran and anything it printed. The blank table has
  the line numbers and empty cells; the key is filled in. A *Scope* column
  appears only when a function was called, and says which function each
  row is inside.

**Variant** (Bugs)
: A copy of the input program with exactly one line changed to introduce
  one error. Each is run, so the key can say *crashes*, *runs but the
  output is wrong*, *hangs* or *no visible change*. Written as
  `<stem>_bug1.py`, `_bug2.py`, …

**Faded (worked) example**
: A complete solution shown several times with progressively more lines
  blanked out, so pupils fill in more each time. Fade produces K versions,
  blanking from the bottom up by default; the key is the full solution.

**Stem**
: The part of a file name before its extension (`program` for
  `program.py`). Outputs are named from it.

## Pseudocode

**ERL (OCR Exam Reference Language)**
: The pseudocode OCR uses in J277 exam papers. Pseudocode translates
  between it, AQA's pseudocode and Python for the GCSE subset and lists
  anything it could not translate instead of dropping it.

**AQA pseudocode**
: AQA's equivalent for 8525: `←` for assignment, `OUTPUT`, `USERINPUT`,
  `ENDWHILE` and the rest.

**GCSE subset**
: The part of Python both boards expect: variables, arithmetic,
  comparisons, `if`, counted and conditional loops, functions, lists,
  strings, casts, random, basic file methods. Outside it, Pseudocode keeps
  the line as a comment and names it in the could-not-translate list.

## Quiz

**Question bank**
: A Markdown file with one `## ` heading per question. Format in
  [Question banks](question-banks.md).

**Spec point / tag**
: A label on a question such as `ocr:1.2.4` or `aqa:3.3.2` (a point in the
  exam board's specification) or `topic:binary`. Topic tags drive filters
  and retrieval; `staff quiz spec ocr` lists the spec points.

**Do-now**
: A short printable starter for the first minutes of a lesson: a few
  questions from the bank in the house style, with the answers in a
  separate key.

**Taught log**
: A CSV of `date,topic`: when each topic was taught. Nothing else goes in
  it.

**Retrieval windows**
: The three dates retrieval mode looks back to: one, three and six weeks
  before today, each with three days' leeway either side. Topics taught
  inside a window are eligible, and the questions are drawn round-robin
  across the windows so each gets a fair share. The run log says what fell
  in each.

## The app

**Tool**
: One panel in the sidebar and one `staff` subcommand over the same code.
  Tools are listed in the order a lesson meets them, and ⌘1–⌘9 follow that
  order top to bottom.

**Resources folder**
: The folder of teaching resources the Resource Library indexes. Read-only
  to every tool: nothing in it is ever changed, and a tool given a file
  from it writes its outputs elsewhere.

**Exclusion list, name only**
: Two Resource Library guards. The exclusion list names folders under the
  resources folder that are neither indexed nor listed. *Name only* marks
  a file whose text looked like pupil details, so only its name went into
  the index. Both in [Privacy](privacy.md).

**Indexed, shown**
: The two library file counts. *Indexed* is every file under the resources
  folder that the exclusion list allows, hidden cruft included; *shown* is
  indexed minus hidden, the size of the tree with *Hidden* off. One tally
  feeds every place a count appears ([Using the launcher](launcher.md#how-files-are-counted)).

**Cloud placeholder**
: A file that a cloud service lists on this Mac but has not downloaded. The
  library marks it and moves on.

**Sessions folder**
: Where Classroom keeps lesson copies (`~/TeachingSessions` by default) and,
  under `outputs/`, where tools without an input file write. Local, never
  auto-detected from a cloud folder.

**Lesson label**
: The one short line (60 characters at most) Classroom asks for when it
  opens a resource for class, such as `P3 Y9 loops`. It names the session
  folder. A lesson, not a class or a pupil.

**Promote**
: Copy a lesson copy's edits back beside the original as a new versioned
  file (`loops_v2.py`, then `_v3`). The original is never overwritten.

**Output folder**
: Where a tool writes. The rule, and every tool's file names, are in
  [Outputs](outputs.md).

**Exam board**
: OCR J277 or AQA 8525, set in Settings (`--board` on the command line for
  one run). Chooses the grade preset Marks starts with and the gates a
  GCSE truth-table worksheet may use (OCR: AND, OR, NOT; AQA adds XOR).
  Quiz spec tags are per question (`ocr:` and `aqa:` can both be on one),
  so they do not depend on it.

**Level** (Worksheet)
: `gcse` or `a_level`, for truth tables. GCSE follows the board; A-level
  adds XOR at every difficulty and NAND / NOR at `hard`, and puts `alevel`
  in the file name so the GCSE sheet with the same seed survives.

**Boolean laws** (Worksheet)
: The family of laws a simplification set practises: `absorption`
  (absorption, distributive, complement; the default), `de_morgan` (adds De
  Morgan), `identities` (identity, idempotent, double negation, complement;
  the only family that puts `X AND X`, `NOT NOT X` or `0` / `1` on the
  sheet) or `all`. The key undoes the question one law at a time, each step
  in the question's own letters.

**Thonny**
: The Python editor on most school machines. Classroom opens copies in it
  by default; IDLE, the system default or any command with `{file}` in it
  can be set instead.

**Run bar**
: The foot of a tool's inputs column: the Run button (⌘↵), the folder the
  tool will write to, *Open output folder* and the one-line result.
