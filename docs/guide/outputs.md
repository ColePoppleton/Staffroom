# Outputs

Where a tool writes, and what it calls the files. Every tool follows the
same two rules, so once you know them for one you know them for all.

## Where files go

The output folder is decided before you press Run, in this order, and the
line under the Run button names it:

1. **The folder set in Settings** (*Settings › Output folder*), if you set
   one. Every tool then writes there.
2. **Next to the input file**, when the tool has one and it is not inside
   the resources folder. A marks file on the Desktop gets its CSVs and
   chart on the Desktop.
3. **`<sessions folder>/outputs/<tool>/`** otherwise: a tool with no input
   file (Worksheet), pasted code, or an input picked from the resources
   folder, which is read-only to every tool. The sessions folder is
   `~/TeachingSessions` unless you changed it, so a worksheet lands in
   `~/TeachingSessions/outputs/worksheet/` and a Parsons sheet made from a
   library resource in `~/TeachingSessions/outputs/parsons/`.

Never the folder the app happened to be started from. Before the first run
the result strip offers **Open output folder**; after a run its **Folder**
button opens where the files went, and each file has a button of its own.
The log line at the end of a run (under *Details*) repeats the folder. From the terminal, `--out <folder>` on
any `make`, `run` or `export` command overrides all three.

A second run with the same input and settings overwrites the previous
files; change the seed or the input name to keep both. Quiz also says so:
when one of its files was already in the folder, the log and the summary
name it (`replaced question_bank_donow_s1.pdf`). It still overwrites rather
than numbering a copy, because the same name means the same bank, kind of
sheet, date and seed: a regenerated sheet, not a second one.

## What files are called

The stem is the input file's name without its extension (`program.py` →
`program`), or `pasted_code` for code typed into the panel. Worksheet has no
input, so its stem is built from its options.

| Tool | Files | Notes |
| --- | --- | --- |
| Marks | `<stem>_distribution.csv`, `<stem>_distribution.png`, `<stem>_questions.csv` | aggregates only; the per-script grades on screen are never written |
| Worksheet | `<topic>_<difficulty>_s<seed>.docx` / `.pdf` and `…_key.docx` / `.pdf` | `binary_medium_s42.pdf`; the seed in the name and in the header regenerates the same set. With *Level* set to A-level the stem is `<topic>_<difficulty>_alevel_s<seed>`, so it never overwrites the GCSE sheet with the same seed |
| Parsons | `<stem>_parsons_s<seed>.docx` / `.pdf` and `…_key` | |
| Trace | `<stem>_trace.docx` / `.pdf` (blank table) and `<stem>_trace_key` (completed) | |
| Bugs | `<stem>_bug1.py` … `<stem>_bugN.py`, then `<stem>_bugs.docx` / `.pdf` and `<stem>_bugs_key` | one `.py` per variant, so a variant can be opened in Thonny as it is |
| Fade | `<stem>_faded.docx` / `.pdf` and `<stem>_faded_key` (the complete solution) | |
| Pseudocode | `<stem>.ocr.txt`, `<stem>.aqa.txt` or `<stem>.py`, by target language | the panel writes unless *Save output* is `none`; the terminal only with `--save` |
| Quiz | export: `<bank stem>_<format>_s<seed>`, so `question_bank_kahoot_s1.xlsx` + `.csv`, `question_bank_forms_s1.txt`, or `question_bank_donow_s1.docx` / `.pdf` + `question_bank_donow_s1_key`. Retrieval: `<bank stem>_retrieval_<date>_<format>_s<seed>`, so `question_bank_retrieval_2026-10-09_donow_s1.pdf` + `_key` | the date is the *As of* date the questions were picked for; a do-now and a retrieval starter from one bank never share a name |
| Classroom | `<sessions folder>/<date>/<lesson label>/<original name>`; *Promote* writes `<original name>_v2.py` beside the original (then `_v3`, never overwriting) | lesson copies, not outputs: they follow the sessions folder, not the rules above |

Every sheet comes from one document model ([house style](house-style.md)):
the pupil-facing file has the stem alone, the answers go in a separate
`_key` file with the same stem, and *Output* (`--format docx|pdf|both`,
default both) chooses the formats. A tool whose document has no answer
section writes no key.

## What the files hold

- **Marks** writes counts, percentages and per-question statistics. No row
  of the input is ever written; see [Privacy](privacy.md).
- **Worksheet, Parsons, Trace, Bugs, Fade and the do-now** carry your
  header and footer text, the title, the topic and the date. Worksheet and
  Parsons print the seed and settings under the title, so a sheet can be
  made again; Trace says how many steps it recorded and whether it hit the
  cap.
- **Bugs' `.py` variants** are the input program with one line changed; the
  key says which line and what the change does.
- **Quiz's Kahoot files** follow Kahoot's import template; the `.csv` has
  the same columns for a look before uploading.

Terms used here (seed, key, distractor, variant, stem) are in the
[Glossary](glossary.md).
