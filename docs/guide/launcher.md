# Using the launcher

The window has two sidebar roots: **Tools** and **Resources**.

The tools are listed in the order a lesson meets them, not alphabetically:
Classroom, Marks, Worksheet, Parsons, Quiz, Trace, Bugs, Fade, Pseudocode.
A fresh install opens on Classroom. (`hello`, the developers' reference
tool, is not in the list; `staff hello` still works from the terminal.)

The very first start shows a card asking for the resources folder; choose
one or skip it and set it later in Settings.

![The first-run card](../first-run-dark.png)

### How files are counted

Every file count the library reports comes from one tally, so the sidebar
footer, the Resources header, `staff library status` and the index summary
always agree. A file is **indexed** when it is under the resources folder and
the exclusion list allows it; the excluded are never counted. Hidden cruft
(`.DS_Store`, `__pycache__`, zips, dot-files), cloud placeholders and files
indexed by name only *are* counted, and reported as subsets rather than
subtracted silently. **Shown** is indexed minus hidden: what the tree lists
with *Hidden* off. So `563 files (24 hidden)  ·  3 name only` means 587 are
indexed, the tree lists 563, and turning *Hidden* on makes it `587 files
(incl. 24 hidden)`. `staff library status` prints the long form:
`587 indexed: 563 shown, 24 hidden, 2 cloud-only, 3 name only`.

Pick a tool, fill in the inputs down the left, press the button at their foot
(or ⌘↵). Results appear on the right, beside the inputs, so you can change one
setting and run again without scrolling; a tool with more than one result shows
them as tabs (Trace: the completed table and the sheet preview). Files are
written to the output folder, which the run bar names before you press Run:
next to the input by default,
`~/TeachingSessions/outputs/<tool>/` for tools with no input file, or
wherever Settings says ([Outputs](outputs.md) has the rule and every tool's
file names). **Open output folder** works before and after the run. The log
at the foot of the results says exactly what happened in that run; the
log drawer (⌘L) and the log file hold the app-wide log, described in
[Privacy](privacy.md#what-the-log-contains).

## Shortcuts

| Keys | Does |
| --- | --- |
| ⌘↵ | Run the tool on screen (its button at the foot of the inputs) |
| ⌘K | Jump to the Resources search box |
| ⌘O | Classroom with the library picker open |
| ⌘1 – ⌘9 | Switch tool, top to bottom: ⌘1 Classroom, ⌘2 Marks, ⌘3 Worksheet, ⌘4 Parsons, ⌘5 Quiz, ⌘6 Trace, ⌘7 Bugs, ⌘8 Fade, ⌘9 Pseudocode |
| ⌘L | Show or hide the log drawer |
| ⌘, | Settings |

## Settings

| Setting | Meaning |
| --- | --- |
| Theme | dark or light |
| Output folder | where tools write; empty means next to the input, or `<sessions folder>/outputs/<tool>` when there is none or the input is in the resources folder |
| Resources folder | what the Resource Library indexes (read-only to every tool), and the folders under it to keep out of the index |
| Sessions folder | where Classroom puts lesson copies; local by default |
| Editor | Thonny, IDLE, system default, or a custom `{file}` command |
| Exam board | OCR J277 or AQA 8525: the grade preset Marks starts with, and the gates a GCSE truth-table worksheet may use |
| Header / footer text | printed on every worksheet and key |
| Logging | the level of the app log (`INFO` by default), and buttons to reveal the config file and the log |
| Updates | check for and apply an update when running from a checkout |

Everything is saved to `~/.config/staffroom/config.toml` as you change it.
Words the panels use without explaining (seed, facility, ERL, do-now…) are
in the [Glossary](glossary.md).

## The command line

Every tool is also a `staff` subcommand with the same options. `staff --help`
lists them; `staff <tool> --help` shows a tool's commands. The CLI is the
primary way the tools are tested, so if something works in the panel it
works in the terminal and vice versa.
