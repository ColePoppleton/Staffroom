# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/). Add a line under **Unreleased**
with every change; `just release <part>` turns it into a version.

## [Unreleased]
### Changed
- The documentation site covers using Staffroom and contributing to it; planning
  notes stay in the repository and are not published.
- The repository is public: the install docs no longer ask colleagues for access,
  and the wheel on each GitHub Release is the fallback when git is not available.
- Ready to be public: the first audit no longer names the owner's real folder or
  index counts, and issue claims no longer record the machine's name.


## [0.8.0] - 2026-10-11
### Added
- Quiz shows the *Taught log* picker only while *Retrieval mode* is ticked, under
  the options it follows, and a hidden log is never handed to the run (#123).
  Any panel can do the same: `PanelSpec.shown_when` hides a whole input while a
  field of an options form (`"options.retrieval"`) or a `Choice` does not hold
  the given values; a hidden input passes its empty value and is not asked for,
  and `core.panel` refuses unknown keys, impossible values and loops when the
  spec is built.
- The Library's column has a **Tags ▾** filter beside *All types* (#111). Its menu
  lists the tags on the files the Library shows, each with how many carry it;
  choosing one narrows the tree (opened all the way down) and the search results
  to files carrying it, and choosing more narrows further. It combines with the
  type filter and the query, follows tag edits in the preview at once, and the
  footer says how many files it leaves. Tags are still read from the sidecar
  (`.staffroom/tags.json`); the resources folder is never written.
  `LibraryService.tag_counts()` and a `tags=` argument on `resources()` and
  `search()` back it, over pure `count_tags` / `paths_with_tags` helpers.

### Changed
- The date in a sheet's header can be pinned with `STAFFROOM_DATE=YYYY-MM-DD` (#107),
  read in one place (`core/export/dating.py`); every sheet builder falls back to it
  instead of reading the clock. `scripts/screenshots.sh` pins it, so the docs pages
  (`docs/output-*.png`, `docs/worksheet-sample.png`) stay byte-identical from day
  to day, and `scripts/screenshots.sh outputs` redoes just those pages. A teacher's
  own runs never set it and still print today's date. `worksheet-sample.png` is
  re-rendered once: it still showed the truth tables from before #43.
- Options forms show only the fields that apply and say their choices in words
  (#91). `OptionsForm` gains `shown_when` (a field shows only while another
  holds given values), `choice_labels` and `switches` (a segmented switch for a
  short choice). Worksheet shows *Level* only for truth tables and *Boolean
  laws* only for simplification, with topic names, *Easy / Medium / Hard* and
  *Word + PDF / Word / PDF*; the quiz shows *Title* only for Forms and do-now
  and *As of* only in retrieval mode; Fade shows *Line ranges* only for *Only
  the lines I list*; Parsons, Trace, Bugs and Pseudocode get readable output
  choices. A hidden field keeps what was set in it, but the tool is handed its
  default, so a value the teacher cannot see never changes or breaks a run.
- `docs/classroom-dark.png` no longer changes every day (#116): the launcher's
  screenshot mode takes `--today YYYY-MM-DD`, which pins only the day Classroom's
  run bar shows (`Copies to …/sessions/<day>`), and `scripts/screenshots.sh` passes
  it `STAFFROOM_DATE`. It is a separate, display-only flag because the session
  folder decides where real lesson copies go: the launcher refuses it without
  `--screenshot`, it is never saved, and *Open for class* always copies into
  today's folder.

### Fixed
- Bugs: a *wrong variable name* bug now swaps in a name a pupil might really
  type (#127): one of the same apparent kind (number, string, list…) that is
  already assigned in the same scope, the most recently assigned first, instead
  of always the program's first name. In `examples/year9.py` that was the list
  `scores`, so seven of the eight wrong-name bugs were TypeErrors; now seven run
  with the wrong output (`if count >= 50:`), and only `for score in score:`
  crashes. Still deterministic, so a seed gives the same sheet.
- Bugs: the key shows an indentation slip (#130). Its two lines used to read the
  same (`count = count + 1` twice) because the key trimmed the indent; now each
  space of indentation shows as `·` when the indent is what changed, and the
  *Bug* cell says how far it moved (*indentation slip (4 spaces to 0)*), in the
  PDF, docx and text key and the panel's *What each bug does* table. The printed
  key adds a one-line legend for the dots.
- Bugs aims for a mix of outcomes (#118): at the defaults all four `year9.py`
  versions crashed, two of them with SyntaxErrors. With two or more versions the
  sheet now includes a *runs, but the output is wrong* bug when the program has
  one, and at most one SyntaxError unless nothing else can make up the count;
  still one bug per version, chosen in the seed's order, so the same seed gives
  the same sheet. A program that cannot offer the mix gets its sheet and a warning.
- Saving settings can no longer leave `config.toml` truncated (#125). The file is
  written to a hidden temporary file beside it and swapped in with `os.replace`,
  so a disk that fills or a folder that turns read-only mid-write leaves the old
  settings whole; the temporary file is removed and the teacher sees the same
  *Settings could not be saved* line as before (#74). The file keeps its
  permissions, a symlinked config stays a symlink, and a config made read-only on
  purpose is still left alone. `usage.toml` and the Library's tags sidecar now use
  the same helper (`core/atomic.py`), so they cannot be truncated either.
- In the Library, the type filter (*All types*) narrows the folder tree too, not
  only the search results (#122): with no query, choosing *python* now leaves just
  the Python files, opened all the way down, as the Tags filter does. Type, tags
  and query always combine, and the footer says what is shown
  (`3 Python files tagged loops`) above the library's own count, which the
  sidebar and the header keep (#30). `LibraryService.resources()` takes `kinds=`,
  and `core/library/filters.py`'s `LibraryFilter` words the footer line.
- A long failure in the result strip is shown whole, and the strip grows to fit it
  (#121). A failure now wraps to as many lines as it needs (up to six; past that it
  is cut between words, with the full text in the tooltip and behind *Details*), so
  a message naming a file path keeps its last sentence: *"… config.toml is
  read-only. You can use it until you quit."* Outcomes still wrap to two lines. The
  strip lays itself out as soon as its text changes, so no frame shows the new
  lines squeezed into the old height, and a path that wraps inside itself no
  longer counts as cut (no needless tooltip).
- `just install` updates an installed Staffroom.app in place (overwriting its files,
  removing ones the build no longer has, then re-signing and re-registering it)
  instead of deleting and recopying it, so Spotlight keeps listing the app rather
  than dropping it until it re-indexes (#79).
- `just release` re-pins the documented install line
  (`git+https://github.com/ColePoppleton/Staffroom@vX.Y.Z`) and the wheel
  filename in README.md and docs/ to the new version in the release commit, so
  the docs no longer go on installing the previous release (#100). The pins now
  point at v0.7.0, and a test holds them equal to the package version.
- Bugs no longer fills a find-the-bug sheet with versions that run exactly like
  the original (#92): at the defaults two of the four `year9.py` variants did.
  Each candidate is run while choosing and a silent one is swapped for the next
  bug in the seed's order, so the same seed still gives the same sheet. *Silent
  bugs allowed* (`--silent N`, default 0) keeps up to N for a read-the-code
  lesson; the key says *silent* and the pupil sheet marks each one *this version
  may run the same: read the code*. When fewer visible bugs exist than asked
  for, a warning and the result strip say so. The seed is now in the sheet's
  header.
- A config home that cannot be written no longer turns Settings changes or
  *Save as preset* in Marks into a bug traceback (#74). `Config.save()` never
  raises `OSError`: it logs one warning per session and returns what went
  wrong, the change still applies until you quit, Settings says "Settings could
  not be saved: <path> is read-only. Changes last until you quit." under its
  title, and Marks says the preset could not be saved in the result strip.

## [0.7.0] - 2026-10-09
### Changed
- Worksheet, Parsons, Trace, Bugs, Fade and the quiz do-now show the PDF the run
  wrote instead of an ASCII rendering of it (#85): *Sheet* and *Key* tabs with
  their page counts, the current page large and whole, thumbnails of every page
  of both down the side (drawn off the GUI thread, and only once they scroll
  into view, so a 17-page bugs sheet opens as fast as one page), *Open PDF* and
  *Print…* (the system print dialog, then the pages as shown). A run told to
  write Word only says so over the text of the sheet, never an empty page. The
  quiz's Kahoot and Forms text moves to a *Paste text* tab shown only for those
  formats; Bugs' table is *What each bug does* and Trace's *Completed table*.
  The command line's `--preview` text is unchanged. The vocabulary gains
  `PagePreview`, `Pages` / `pages_from`, `RunResult.pages` and
  `TextView.optional`; screenshots take `--tab` and `--option field=value`.
- The five code tools (Parsons, Trace, Bugs, Fade, Pseudocode) take their program
  in one input (#86): a chip naming the file (its Library path, *Change ▾* for From
  library or Browse) over the program itself, read-only, highlighted and numbered
  the way the sheets number it, instead of a *Python file* picker and an empty
  *Or paste code* box. *Paste instead* empties the view for a paste; *Use a file*
  goes back. It is not an editor: a file saved again in Thonny is shown again and
  the run reads it afresh. Trace's table and the Bugs key point at the program:
  click a row and its line lights up, click a line and its rows are selected.
  Pseudocode shows the source beside the translation (numbered too), the
  could-not-translate notes under it; *Language* under the file follows the
  guess the moment a file is chosen or code pasted (#62), and *To* moves off it.
  The vocabulary gains `CodeSource` (value `CodeValue(path, text)`, read by
  `core.codeinput`), `ResultsTable.line_column`, `TextView.code` and
  `PanelSpec.suggest`.
- The Library hands a file to a tool (#88). It is one page: the tree and search
  in one column (search results replace the tree while there is a query), the
  file beside it with its tags as chips (*+ tag* inline, × to remove, the note
  behind one link) and a use bar: *Open for class* with the lesson label typed
  inline (Enter or ⌘O opens it), then one button per tool that takes this kind
  of file (`.py` → Parsons, Trace, Bugs, Fade, Pseudocode; `.md` → Quiz;
  `.csv`/`.xlsx` → Marks), each opening the tool with the file already picked.
  Opening a file for class from the Library is 3 actions instead of 8 and runs
  Classroom's own `run`, so the original is never touched. The buttons come
  from each tool's main file input (`core.panel.main_file_input`), so a new tool
  appears with no library change; `filter_ext` (ResourcePicker, CodeSource) may name several
  extensions. Office files keep *Open externally* as the main action. A long
  resources-folder path no longer widens the window past its minimum (#103).
- A run's result is one strip along the top of the output pane (#84): a tick or a
  cross, a short outcome ("10 questions · seed 42", or the failure in plain words),
  one button per file written (*PDF Sheet*, *PDF Key*, *DOCX Sheet* …; click opens
  it in its app, right-click shows it in Finder) and a *Folder* button. Warnings
  (marks, quiz, bugs, pseudocode) show as "3 warnings ▸" that opens the list. The
  per-panel Log card is gone: the run log sits behind a one-line *Details ▸* footer,
  closed by default and remembered per tool for the session. The foot of the inputs
  is the Run button and where it writes; the truncated status line and the second
  "Writes to" label are gone. Tools say what they made with `RunResult.outcome`,
  may name a file's button with `RunResult.labels`, and raise warnings with
  `ctx.warn()`; `staffroom --expand` opens the warnings for a screenshot.
- Every tool is now a workbench (#83): the inputs in a 390 px column on the left
  with the run button pinned at its foot (⌘↵ runs it from anywhere in the
  window), the results filling the right, tabbed when a tool has more than one
  (Trace: *Completed trace table* · *Preview*). Lists to act on and notes sit
  under the main result; inputs are hairline-separated groups instead of a card
  each. Nothing scrolls on its own any more and the inputs stay beside the
  result, so the first result is in view after a run in 9 of 9 tools at
  1240×780 (2 of 9 before). A panel can mark an output `place="main"` or
  `"below"` (`core.panel`); the header loses the version chip.
- The sidebar and the app's identity are redesigned (#89). The brand row (mark,
  *Staffroom* in Fraunces, a settings gear), a library search field, then the
  places grouped by a teacher's week: **Lessons** (Library, Classroom),
  **Sheets & quizzes** (Worksheet, Quiz), **From a program** (Parsons, Trace,
  Bugs, Fade, Pseudocode), **After a test** (Marks). One line per tool with a
  monochrome glyph instead of a red letter badge and a truncated description
  (the description is the tooltip). The Library is a place in the sidebar, not
  a Tools/Resources mode switch, with its tree and search in their own column.
  The red accent marks only where you are, primary buttons, links and focus.
  The footer has the version with *up to date* or an *update* link, and
  **Activity log**. The theme switch moves to Settings only (plus ⇧⌘L).
  ⌘1–⌘9 follow the new order: Classroom, Worksheet, Quiz, Parsons, Trace,
  Bugs, Fade, Pseudocode, Marks (the Library is ⌘K). Group and glyph are
  optional plugin data (`group`, `glyph`, read like `order`); a tool without
  them is listed under **Other**. The app now uses the brand type, bundled
  under the SIL OFL with their licences: Source Sans 3 for text, Fraunces for
  titles, IBM Plex Mono for code and logs.
- The docs home page leads with what a teacher gets (#90): a headline, the
  pinned two-line install, and a fan of real first pages (worksheet, trace
  table, Parsons) above the fold at 1240×780 in both colour schemes; a
  three-column privacy strip (stored / never stored / check it yourself) whose
  every claim is tested against the Privacy page; and a *What comes out*
  gallery with one real output per tool. The pages are rendered from the
  example files by `just screenshots`. The site nav puts the teachers' pages
  first (Install, Tools, Privacy, Guides, as header tabs) and puts the
  contributor pages in one *Contributing* section at the end.
- Marks is a one-screen report (#87): after *Analyse*, four headline tiles
  (scripts, mean %, median grade with how many reached grade 4, the questions to
  reteach first), the grade chart with counts and percentages under the bars
  beside **one** question table sorted hardest first with an inline facility bar
  and the reteach rows tagged, and the per-script grades folded under "view only,
  never saved". 5.2 screens → 0.87 at 1240×780 (20 questions: 1.54). The
  separate distribution table (now *Table* on the chart) and "Worst questions"
  card are gone; the saved CSVs are unchanged and still aggregates only. Inputs:
  the file as a chip with what was found in it instead of an 11-row preview, and
  the boundaries as a 5 × 2 grid with the preset and a % / raw switch. New in the
  vocabulary and kit for any tool: `StatTiles`, `BarChart`, `ResultsTable` bars,
  tags and folding, `main_layout="row"`, compact `EditableTable` and
  `TablePreview`, `Choice`, `FilePicker(chip=True)`. The CLI prints the same
  headline; the saved chart gains the percentages too.
- CI and the release workflow run on macOS again: the repository is public, so
  macOS runners are free, and the layout and packaging tests are written for the
  platform Staffroom targets.

### Fixed
- `staffroom --settings` no longer leaves the last tool highlighted beside the
  Settings page (#89): every route to a page now sets the sidebar from what is
  shown.
- Classroom's **Past sessions** no longer lists the tools' shared output folder
  (#97). A worksheet made with no input of its own goes to
  `<sessions folder>/outputs/worksheet/`, and it showed up as a lesson on day
  `outputs` with Diff and Promote buttons. Only real sessions are listed now: a
  date-named day folder holding lesson folders with a `.origin.json`
  (`classroom.logic.is_session_folder`); stray files and hand-made folders are
  left out too.
- Quiz no longer overwrites one kind of sheet with another (#82). A retrieval
  run is named for its date, `question_bank_retrieval_2026-10-09_donow_s1.pdf`,
  and every export carries its seed, `question_bank_donow_s1.pdf`,
  `question_bank_kahoot_s1.xlsx`, `question_bank_forms_s1.txt`, so a do-now and
  the retrieval starter made after it both stay in the folder. A run that
  replaces a file of the same name still overwrites it, but the log and the
  summary now name it (`replaced question_bank_donow_s1.pdf`).
- Classroom's run bar now says where **Open for class** really puts the copy,
  *Copies to ~/TeachingSessions/<today>/<label>*, following the label as it is
  typed, and its *Open sessions folder* link opens that folder (created on
  demand) instead of an output folder the copy never goes to (#81). A tool can
  name its own destination with `PanelSpec.writes_to` (`core.panel.WritesTo`);
  every other tool still shows *Writes to* its output folder. A row action such
  as Promote no longer moves the run bar's folder.

- The docs home page, the Install guide and the README now install from GitHub,
  pinned to the latest release:
  `uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@v0.6.0`
  (#80). They used to lead with installing by name from PyPI, where Staffroom
  is not published, so the first instruction failed. The Install guide says
  plainly that the repository is private for now, so the line works only for
  an account that can see it, and Updating explains that a pinned install is
  upgraded by re-running the line with the newer tag. `--python 3.12` stops uv
  picking an older Python that Staffroom cannot run on. A new test fails if the
  README or docs tell anyone to install by name while `extra.published_on_pypi`
  in mkdocs.yml is false, and the *Install line* workflow runs the documented
  line in CI.

## [0.6.0] - 2026-10-09
### Added
- Trace has a Preset dropdown with **Full trace** (the default, as before) and
  **Year 9** (#33): the Year 9 preset turns on the new *Top-level variables
  only* option (`--top-level-only` on the CLI), which leaves out the lines run
  inside functions and their locals, so the sheet has no Scope column and only
  the program's own variables. Every trace sheet now names its preset in the
  header (Full trace, Year 9 or Custom) so a teacher can tell which one they
  handed out. Presets for an options form are part of the shared panel
  vocabulary (`OptionsForm.presets`, `core.panel.preset`) and widget kit, so
  any tool can offer them.
- The launcher shows the running version: the sidebar header reads
  `v0.5.0 · 9 tools`, and Settings › Updates says `Running Staffroom 0.5.0`,
  adding the branch and short commit off a release tag (`0.5.0 (dev, a1b2c3d)`).
  `packaging/make_launcher.py` writes the package version into the bundle's
  `CFBundleShortVersionString` and `CFBundleVersion`, so Finder's Get Info
  matches after `just install` (#69).

### Changed
- `classroom` promote compares the copy with the original and with the latest
  promoted version before writing: an unchanged copy makes no new file and
  the message says `Already promoted as year9_v2.py` (or that it matches the
  original). The CLI exits 0 and prints no path when nothing was written (#32).
- `quiz` names any taught-log column other than `date` and `topic` in the run
  log (`ignored column 'room' — the log is date and topic only`), by header
  only; the column's contents are never read or shown (#32).

### Fixed
- `quiz` reads the taught log through `core.csvio.read_table` like every other
  table, so an identifier column (`name`, `class`, …) is dropped before the
  tool sees it, with the usual dropped-column warning and a run-log line by
  header only (#68). It used to parse the file as raw text, bypassing the
  privacy filter. A new boundary test fails if any tool reads a `.csv`/`.xlsx`
  without `core.csvio` (raw `open`/`read_text` of a table path, `csv.reader`,
  `openpyxl.load_workbook`, or csvio's unfiltered `read_csv`/`read_xlsx`).
- The launcher opens when the config home cannot be written (#65). It used to
  die in `LibraryDB` with `sqlite3.OperationalError: unable to open database
  file`. The library now opens the last index read-only, or an empty
  in-memory database when there is none, and says *Resource Library
  unavailable: cannot write <path>* once in the log, in the Resources sidebar
  and header, and in `staff library status` (exit 0). Re-index is disabled,
  `staff library index` and `search` exit 1 with that line, and every tool
  still runs. The window's own settings (last tool, sidebar mode, theme)
  last for the session with one warning instead of a traceback per click.
- `staff` no longer dies with a `PermissionError` traceback when the config
  home (`~/.config/staffroom/` or `STAFFROOM_HOME`) cannot be written (#60).
  `setup_logging` used to create `logs/` and open the log file with no
  fallback, before any command ran; it now carries on with stderr alone and
  prints one warning line naming the file it could not open. The launcher
  takes the same path, so its startup gets the same fallback.
- `worksheet` refuses a count outside 1–60 with one sentence ("Questions must
  be between 1 and 60 (you asked for 0).") instead of writing an empty sheet
  and key; the CLI and the panel share the limits (#31). Boolean
  simplification questions are now built from textbook forms only (absorption,
  the distributive pair, the redundancy form `A AND (NOT A OR B)`, De Morgan
  over two literals) within a size budget per difficulty, so a hard three-step
  question reads `(A OR (A AND C)) AND NOT (A AND NOT B)` rather than a form
  nested three deep; each key practises more than one law and a sheet never
  repeats a question. GCSE truth tables get one shape per difficulty (one
  gate, two gates, three gates or a `NOT` over a bracket), so medium and hard
  sheets no longer look the same. Keys stay reproducible from the printed seed.
- `staff usage` now counts CLI runs as well as launcher runs (#28): every
  `staff <tool> <command>` that finishes without a `ToolError` is recorded by
  the one wrapper in `cli.py`, so no tool needs its own call. The total stays
  one number per tool, with the launcher's and the CLI's shares shown beside
  it; older files (launcher-only) need no migration. Nothing is recorded when
  the config is `read_only` or the home folder cannot be written, and a
  failed write never fails the command.
- Pseudocode works out the input language from the code itself when `--from`
  is not given, instead of calling every non-`.py` file OCR ERL (#27): `def`
  and `:` blocks mean Python, `endif`/`next`/`then` mean OCR, `←`/`OUTPUT`/
  `USERINPUT` mean AQA, with the file name as the tie-breaker. The log and
  summary say what was decided ("Treated input as AQA pseudocode (guessed
  from the code)"); code with nothing to go on, or that already looks like
  the target, stops with a message naming the `--from` to pass. The panel's
  single *Direction* is now *From* (default `guess`) and *To*.
- `marks` grades a whole cohort in well under a second: `discrimination()`
  computed every script's total once per comparison, which took a minute for
  3,000 rows. Fixed quietly in 0.4.0 by #12; now measured and guarded by tests
  (3,000 × 30 marks analysed in 0.15 s) (#29).
- The library's file counts agree everywhere (#30). The sidebar said "563
  files" and the Resources header "587 files indexed" because one left out
  hidden cruft and the other did not; a pending exclusion widened the gap.
  Both now show the one line `LibraryService.counts()` produces, `563 files
  (24 hidden)  ·  3 name only`, with the hidden shown as a subset instead of
  silently dropped, and `staff library status` and the index summary print
  the same tally in long form (`587 indexed: 563 shown, 24 hidden, 2
  cloud-only, 3 name only`). The definition is in the launcher guide.

## [0.5.0] - 2026-10-09
### Fixed
- Audited every `QListWidgetItem` the shell reaches for the stale-wrapper hazard
  behind #49 (#54): the tool list, the string-list editor and the library result
  lists are safe as they stand, because PySide invalidates row wrappers on
  `QListWidget.clear()` and with the list, and `item(i)` wrappers never outlive
  the call that made them. Each site now says why, and
  `tests/shell/test_lifetime.py` pins the wrapper counts for all three.
- Fade no longer makes duplicate or blank-free versions when asked for more
  versions than there are fadeable lines (#24): versions are capped at the
  fadeable-line count with a log note, so every version has at least one
  blank and strictly more than the one before. A file that is not valid
  Python is refused with the same "That is not valid Python: … (line n)"
  message as the other tools. Range mistakes say what is wrong: lines past
  the end of the file or below 1, ranges typed without choosing the `ranges`
  order, and listed lines that are headers, comments or blank (skipped with
  a log note, or an explanation when nothing is left to fade).
- `staff update` and Settings › Updates compare the checkout with the released
  branch (`origin/main`, or `release_branch` in config) whatever branch it is
  on, and name the newest release tag when one is ahead (#25). A checkout on
  another branch ("on dev; releases are on main"), with no upstream, or
  detached gets one plain line instead of git's "ambiguous argument" error;
  the release is reported but never pulled from there, and the update never
  switches branch.
- Quiz's Kahoot export reports what it actually wrote (#23): the summary and
  the chosen-questions table describe the rows in the file ("3 of 5 written;
  2 short answers skipped: Q5, Q7"), every skipped question has its reason in
  the log, and an export that would be empty stops with a message instead of
  writing a file. Short-answer distractors are now borrowed from the whole
  bank rather than only the chosen questions, nearest first (same topic tag,
  then the same spec section, then anywhere), and the log names the source
  question and topic whenever one had to come from outside the topic.
- The launcher no longer crashes or aborts around a running library index
  (#49, #40). The Resources tree is built through model indexes instead of
  `QStandardItem` objects, whose Python wrappers outlived the items and made
  the next Qt object at that address come back as the wrong type (the flaky
  `'QStandardItem' object has no attribute 'selectionChanged'` on CI).
  Closing the window, a `--screenshot` run and the test fixtures now stop a
  running index at its next file and wait for every worker thread
  (`MainWindow.wait_for_workers`), so Qt never destroys a running `QThread`;
  an index stopped early keeps what it has done and finishes on the next
  launch. `ActionTable` ignores a refresh that arrives after its view is gone.

### Changed
- Docs screenshots redone after the sidebar reorder and the first-run card
  (#46): every image the docs reference shows the workflow-ordered sidebar
  without `hello`; `just screenshots` now runs `scripts/screenshots.sh`,
  which renders the whole set offscreen from a throwaway `STAFFROOM_HOME`
  and the invented fixture resources in `scripts/screenshots/resources/`.
  Ten unreferenced PNGs are gone; the first-run card and the Marks warnings
  run are now shown in the guide.

## [0.4.0] - 2026-10-08
### Added
- First run asks for the resources folder (#18). With no folder set, the
  launcher opens on one card, "Choose your resources folder": Choose… opens a
  folder dialog (at the home folder; the app never suggests a folder, cloud or
  otherwise), the sessions-folder default is shown as text, and a sentence
  points at Settings and the privacy guide's "What the Resource Library
  stores". Choosing a folder saves it, runs the first index with progress on
  the card and lands on Classroom; "Not now" lands there too and leaves the
  "No folder chosen: set it in Settings" hint in the Resources sidebar.
  `FirstRunCard` joins the widget kit; `staffroom --first-run` shows the card
  for screenshots. `staff library index` / `search` with no folder set now say
  where to set it (the Settings page and the `resources_root` key) instead of
  "resources root not found: ".
- Library privacy (#17): an exclusion list for the resources folder (Settings,
  `staff library exclude`, or `<root>/.staffroom/ignore`) whose paths are
  neither indexed nor listed and whose changes re-index; files whose text
  looks like pupil details (candidate number, surname, UPN, date of birth
  next to a value) are indexed by name only, counted in the index summary,
  the sidebar status and `staff library status`, and flagged in the preview;
  Settings and `docs/guide/privacy.md` state what is indexed, where the
  database lives, that the folder is only read, and how to delete the index.
  `StringListEditor` joins the widget kit; `staffroom --settings` opens
  Settings for screenshots.
- `examples/marks_messy.csv`: a fake marks file on which every `marks`
  warning fires, for trying the tool and for the tests.

### Changed
- Parsons and bugs sheets print on fewer pages (#22): Parsons blocks are
  numbered cut-out boxes, two across, with dashed cut lines and the answer
  grid on the same page (`year9.py`, 15 blocks: 2 pages → 1); the bugs sheet
  puts two versions on a page (4 versions: 4 pages → 2). `core.export` gains
  `BoxedBlocks` and `AnswerGrid` for every tool, rendered to docx, PDF and
  text; `examples/year9.py` is the program the page-count tests measure.
- `marks`: the saved distribution chart is always print-friendly: white
  background and the light palette's ink, whatever `general.theme` is.
  The panel shows the same file (#13).
- The sidebar lists tools in workflow order (classroom, marks, worksheet,
  parsons, quiz, trace, bugs, fade, pseudocode) instead of A–Z, and ⌘1–⌘9
  follow it, so a fresh install opens on Classroom and ⌘1 is Classroom.
  `hello`, the developer reference tool, is hidden from the launcher: it
  keeps its CLI, its tests and its place as the `staff new` model, and
  `staff list` shows it marked `[hidden]`. Plugins may declare optional
  `order` and `hidden` attributes (`docs/adding-a-tool.md`); tools without
  them need no change. `just screenshots` now renders the marks tool. (#15)
- Input mistakes are one-line messages for the teacher, never tracebacks
  (#14). `read_table` raises `ToolError` for the wrong kind of file, a missing
  file, a CSV that is really a binary file or a damaged workbook, naming the
  file and what is accepted, so every tool, the CLI and the launcher show the
  sentence; `code_from_inputs` does the same for code files; every tool CLI
  command turns a `ToolError` into a red line and exit 1 without per-command
  `try` blocks. `fade --ranges abc`, `marks --max 4,6,x` and the quiz "as of"
  date say what was expected instead of `invalid literal for int()`.
- Outputs never land in the code checkout or the shell's current directory.
  With no output folder set and no input file, tools write to
  `<sessions folder>/outputs/<tool>/` (created on first write); the run bar
  names the folder before Run and "Open output folder" works at any time;
  Settings explains the default. Screenshot runs (`just screenshots`) write
  to a throwaway folder, so `git status` stays clean. (#11, #10)
- A docs page, *Running pupil code*, that says what a trace / bugs run is
  limited to and what it does not stop (`os.system`, file writes, computed
  import names); the Trace, Bugs and Fade panels point to it (#16).
- Docs for a teacher who is not the owner (#19): the Privacy page lists the
  identifier filter's header words and what passes through (per-pupil flag
  columns such as SEN/PP/EAL reach the preview and are never saved), what the
  run log and the app log file hold and where the file is, the full table of
  what is stored where (including `.origin.json`), and how to delete
  everything; a new *Outputs* page gives the output-folder rule and every
  tool's file names; a new *Glossary* covers facility, discrimination, seed,
  ERL, Parsons problem, faded example, do-now, retrieval windows and the rest;
  the launcher page shows the workflow-order shortcuts and the tool pages
  name their files and link across.

### Fixed
- Worksheet truth tables never set a degenerate question: every input the
  table lists is used, no gate is fed the same input twice, and Q is neither
  constant nor just one input. Gates follow the exam board (OCR J277: AND, OR,
  NOT; AQA 8525 adds XOR); a new **Level** option, `a_level`, adds XOR and,
  at hard only, NAND and NOR. Boolean simplification wraps one letter at a
  time so questions read like a textbook, no longer sets `X AND X`,
  `NOT NOT X` or `0`/`1` unless the new **Boolean laws** option is
  `identities`, and every key step is written in the question's own letters
  (`absorption: B AND (B OR NOT C) = B, leaving A AND B`). The header states
  the gate set or the law family so a sheet is self-describing, and an
  A-level sheet carries `alevel` in its file name (#20).
- `trace`: a program that calls `input()` with the Inputs box empty (or
  short) stops with "`<file>.py` asked for input but the Inputs box is empty:
  add one line per input() call" and writes nothing, instead of a green
  status and a one-row sheet. The tracer records the `EOFError` that
  `input()` itself raised, so a program that catches the EOF, or raises its
  own, is not mistaken for it. Any other runtime error still produces the
  sheet, and the status line now says "ended with <Error>" as the log did
  (#21).
- `marks` finds the `MAX` row of a markbook export even when the flag sits in
  the name column: `core.csvio.read_table(path, flag=...)` decides which rows
  carry the word on the raw file and passes only the row indices on
  (`Table.flagged_rows`); the identifier filter itself is unchanged and still
  unconditional. The tool now warns, in the CLI and the panel log, on a mark
  above its max (question, count, highest), a max of 0, blank or non-numeric
  cells (`ab`), and grade boundaries above the paper total (a percent preset
  applied as raw marks). Blank cells count as 0 in a script's total but are
  left out of facility and discrimination instead of dragging them down, and
  the distribution gains an "Incomplete scripts" row saying how many scripts
  had one. The run still succeeds; the summary says how many warnings to read.
- The runner caps captured stdout and stderr at 1 MB each and drains the
  rest, so a `while True: print(i)` no longer captures hundreds of megabytes
  before the timeout kills it; capped output ends with
  `[output truncated at 1024 KB]` and the trace and bugs keys say so. The
  tracer caps the program's output inside the run too. The import check now
  also catches `__import__("socket")` and `importlib.import_module("socket")`
  with a literal name (#16).

## [0.3.0] - 2026-10-08
### Changed
- Renamed to **Staffroom**. The package is `staffroom`; the commands are
  `staff` (CLI) and `staffroom` (launcher), with `tt` and `tt-gui` kept as
  aliases for one release. Config moves to `~/.config/staffroom/` and is
  copied from `~/.config/teaching-tools/` on first run (the old folder is
  left alone); resource tags live in `<root>/.staffroom/tags.json` and an
  old `.teaching-tools` sidecar is still read. Environment variables are
  `STAFFROOM_HOME` and `STAFFROOM_BOOKLET_DIR`.
- New brand: the door-ajar mark, a manila / navy ink / red-pen colour scheme
  in both the dark and the light theme, and an icon, icns and favicon
  rendered from the SVG with QtSvg (`scripts/make_icon.py`). The docs site
  uses the mark, the scheme and Fraunces / Source Sans 3.
- The thin launcher is `Staffroom.app` (`uk.staffroom.launcher`, executable
  `staffroom`). The repository and docs URLs are unchanged until the GitHub
  repo is renamed.
- The repository is now github.com/ColePoppleton/Staffroom and the docs
  site is colepoppleton.github.io/Staffroom/ (the old URLs redirect).

### Fixed
- The thin launcher no longer runs under Rosetta when opened from Finder
  (`LSRequiresNativeExecution`, `arch -arm64`), which made the arm64 wheels
  fail to load, left only three tools discovered and took a minute to start.
  The bundle is ad-hoc signed (Spotlight ignores an unsigned one), the
  build in `dist/` is unregistered and the installed copy registered with
  Launch Services and Spotlight, and the app icon keeps the macOS inset
  instead of drawing oversized.

## [0.2.0] - 2026-10-08
### Added
- Documentation site (MkDocs Material on GitHub Pages): install, launcher,
  privacy, updating, one page per tool, file formats, process.

### Changed
- Personal references generalised; the resources folder is empty until set
  in Settings; the booklet round-trip test reads `TT_BOOKLET_DIR`.
- Thin launcher app (`just install`) and self-update from the git remote.
- Semantic versioning, Keep-a-Changelog, tag-driven GitHub Releases with a
  wheel and sdist (`.github/workflows/release.yml`, `scripts/release.py`,
  `just release`). `uv tool install` is the canonical install.
- MIT licence.

## [0.1.0] - 2026-10-08

The seven roadmap phases, as built:

### Phase 7 — polish and packaging (2026-10-08)

- Installed as a thin launcher: `just install` builds `Teaching Tools.app`
  whose executable runs the checkout with uv, and copies it into
  /Applications. Nothing to rebuild on a code change.
- Self-update: `tt update` (and `--check`), an Updates card in Settings
  (check / update now), a startup check with an "Update available" notice
  in the sidebar. Fast-forward only; a dirty tree or diverged branch is
  reported, never overwritten. Tested against a local bare remote.
- The PyInstaller bundle is still available as `just bundle` for a machine
  without the repo.
- Code now lives at github.com/ColePoppleton/Teaching-Tools (private).
- App icon (drawn by `scripts/make_icon.py`, `just icon`): icon.png for the
  window and Dock, icon.icns for the bundle.
- Theme check: every panel rendered in dark and light offscreen; no fixes
  were needed beyond what earlier phases already settled.
- Shortcuts: ⌘K jumps to the Resources search box, ⌘O opens the classroom
  tool with the library picker, ⌘1–⌘9 switch tools, ⌘L toggles the log,
  ⌘, opens Settings. Sidebar tooltips show them.
- Settings now covers the resources folder, the sessions folder, the editor
  command, the exam board (sets the default marks preset and tags) and the
  house-style header and footer text printed on every worksheet and key.
- `just app` builds `dist/Teaching Tools.app` with PyInstaller from
  `packaging/tt-gui.spec` (tools, assets, spec files and the tracer are
  collected explicitly because discovery is dynamic).
- `tt usage`: run counts and last-used dates per tool, recorded by the
  launcher and nothing else, so "which tools were actually used this
  month" can be answered from evidence.

### Phase 6 — quiz (2026-10-08)

- `core/spec/`: OCR J277 and AQA 8525 content maps as TOML data files with a
  loader (`load_taxonomy`, `find`, `describe`). Indicative: check against
  the current specification.
- `tools/quiz`: Markdown question banks (`## ` per question; `type: mcq |
  short | tf`; `tags:` with spec codes and `topic:` tags; `- [x]` options;
  `answer:`; `time:`; `why:`), validated with line-numbered errors.
- Exporters: Kahoot (.xlsx in the template layout, headers on row 8 and
  data from row 9, plus a .csv with the same headers; 120/75-character
  limits enforced, times snapped to Kahoot's allowed values, true/false as
  two options, short answers given three borrowed distractors or skipped
  with a note), Forms paste text with a separate answers block, and a
  printable do-now through the house style with the key split off.
- Retrieval scheduler: a `date,topic` taught log (never a class or a pupil)
  picks questions from topics taught 1, 3 and 6 weeks ago (± 3 days),
  round-robin across the three windows.
- CLI: `tt quiz export --bank B --format F --topics T --spec S --n N`,
  `tt quiz retrieval --bank B --log L --date D`, `tt quiz list`,
  `tt quiz check`, `tt quiz spec ocr|aqa`.
- Examples: `question_bank.md` (13 invented questions) and `taught_log.csv`.
- Manual check still owed: import `question_bank_kahoot.xlsx`
  into Kahoot once and confirm it accepts the columns.
- Banks are Markdown (and could be TOML) rather than YAML, to avoid a
  dependency.

### Phase 5 — pseudocode (2026-10-07)

- `tools/pseudocode`: Python ↔ OCR Exam Reference Language ↔ AQA pseudocode
  for the GCSE subset, through one intermediate representation. Covers
  variables, arithmetic (`DIV`, `MOD`, `^`), comparisons, `AND/OR/NOT`,
  if/elif/else, count loops, for-each, while, do…until / REPEAT…UNTIL,
  functions and procedures, lists and indexing, string length / substring /
  upper / lower, casts, random, basic file methods and comments.
- Anything outside the subset is kept as a comment in the output and listed
  under "Could not translate"; translations with a caveat (for-each in ERL,
  `.append` on fixed arrays, AQA `USERINPUT` losing the prompt) are listed
  as notes. Nothing is dropped silently.
- Both pseudocode dialects parse back to Python, so Python → ERL → Python
  round trips. Every OCR Booklet program 1a-8c round-trips to an
  ast-equivalent program (tested against the real files when present and
  against embedded copies always).
- Panel: file or pasted code, direction dropdown, translation pane with a
  Copy button, report pane. CLI `tt pseudocode to-ocr | to-aqa | to-python
  <file> [--from] [--save] [--out]`.
- Widget kit: `TextView(copy_button=True)` adds a Copy button to any text
  output.

### Phase 4 — sandboxed runner, trace, bugs, fade (2026-10-07)

- `core/runner/`: runs a file with `python -I -u` in a temp working
  directory with a minimal environment, hard wall-clock timeout (the process
  is killed and reported), CPU rlimit as a second guard, captured output,
  optional stdin, and an AST refusal of networking and subprocess imports.
  Not a security boundary, by design: these are the teacher's own files.
- `tools/trace`: a tracer runs inside the sandbox under `sys.settrace`,
  recording each executed line of the program with the variable values after
  it and anything printed, capped at N steps. Filter which lines are
  recorded (assignments, loop headers, ifs, calls) and which variables are
  columns. Sheet: numbered listing plus blank table; key: completed table and
  the program output. Functions get a Scope column.
- `tools/bugs`: seven error classes (comparison flipped, off by one, missing
  colon, missing bracket, wrong variable name, indentation slip, string /
  integer confusion). N variant files with exactly one mutation each; every
  variant is run in the sandbox against the original so the key says
  crashes with X, output wrong, hangs, or no visible change.
- `tools/fade`: K progressively faded versions (bottom-up, top-down or by
  line ranges; headers kept by default), one document with a page per
  version and the solution as key.
- `core/codeinput.py`: shared "file from the library or pasted code" input.
- CLI: `tt trace make`, `tt bugs make` / `tt bugs kinds`, `tt fade make`.

### Phase 3 — house style, parsons, worksheet (2026-10-07)

- `core/export/`: one document model (headings, paragraphs, code blocks,
  numbered items with answer space, tables, hint boxes, page breaks; answer
  sections) rendered to docx (python-docx), PDF (reportlab) and plain text.
  Header with title / topic / date, footer with page numbers, monospace code.
  `export()` writes `<stem>.<fmt>` and `<stem>_key.<fmt>`.
- `tools/parsons`: a .py from the library (or pasted) → blocks at statement
  level (compound headers and bodies apart) or per line, seeded shuffle,
  distractors by mutating a line (missing colon, wrong comparison, off by
  one), indentation shown or stripped, optional hint box. Key gives the
  order, the distractors and the reconstructed program. Tests prove the key
  rebuilds an ast-equal program for seven program shapes and 39 seeds.
- `tools/worksheet`: nine seeded generators (binary/denary/hex, two's
  complement, binary addition with overflow, shifts, truth tables, Boolean
  simplification with laws listed, file sizes, run-length encoding, Huffman
  weight). The seed, difficulty and count sit in the sheet header so a set
  can be regenerated. Every generator is verified by independent computation.
- CLI: `tt parsons make <file> --seed N --distractors K [--lines]
  [--no-indent] [--format]`, `tt worksheet make --topic T --count N --seed S
  [--difficulty]`, `tt worksheet topics`.
- Widget kit: `TextArea` input for pasted code.
- python-docx and reportlab added.
- Fixed: outputs for an input that lives in the resources folder were being
  written next to it. The resources folder is read-only to every tool, so
  those outputs now go to `~/TeachingSessions/outputs` unless an output
  folder is configured.

### Phase 2 — marks (2026-10-06)

- `tools/marks`: raw marks per question (q1..qn, one row per script, no
  identifiers) → per-script grades (view only), grade distribution table
  and bar chart, facility index and discrimination (top third vs bottom
  third) per question, worst-N questions to reteach.
- Max marks from a row flagged `MAX`, from the Max marks option, or (with a
  warning) the highest mark seen per question.
- Grade boundaries: editable grid as % of paper or raw marks, with built-in
  starting points for OCR J277, AQA 8525 and A-level, and "Save as preset"
  persisted to `config.tool("marks")["presets"]`.
- Saved outputs are aggregates only: `<stem>_distribution.csv`,
  `<stem>_questions.csv`, `<stem>_distribution.png`. Nothing per script is
  written; identifier columns are dropped and logged before analysis.
- CLI: `tt marks run <file> [--preset] [--unit percent|raw] [--max] [--worst]
  [--out]`, `tt marks presets`.
- Widget kit: `EditableTable` gained presets (dropdown, Apply, Save as
  preset backed by a plugin action). `ImageView` now scales to the card
  width instead of forcing the panel to the image's size.
- Colour tokens moved to `core/theme_tokens.py` so charts can use the app
  palette without a tool touching Qt. matplotlib (Agg) added.

### Phase 1b — classroom (2026-10-06)

- Library picker rebuilt as a palette after the first version proved
  unreadable: one big search field, the folder tree while it is empty, rich
  rows (name, type, folder, snippet) while typing, arrow keys and Enter to
  choose, name-substring fallback for things FTS misses. The picker field
  then shows the library-relative path rather than a long absolute one.
  Generic list, tree and dialog styling added to the theme so nothing falls
  back to Qt defaults again.
- `tools/classroom`: "Open for class" copies a resource to
  `<sessions_root>/<YYYY-MM-DD>/<label>/<file>`, records the origin in a
  `.origin.json` sidecar beside the copy, and launches the configured editor
  on the copy. Opening the same file for the same lesson re-opens the
  existing copy; edits are never overwritten. The original is only ever read.
- Session browser: past copies with Diff vs original (unified diff), Re-open,
  and Promote, which copies the edit back next to the original as
  `<name>_v2.py` (then `_v3`, never overwriting). The library picks the new
  file up on re-index.
- Sessions folder defaults to local `~/TeachingSessions`; a folder picker in
  Settings covers syncing elsewhere. No cloud-folder detection, by decision:
  which folder is reachable from school is the teacher's decision.
- Editor: `core/launch.py` turns a `{file}` command template into argv.
  Presets Thonny (`open -a Thonny {file}`, default), IDLE
  (`python3 -m idlelib {file}`), System default (`open {file}`), or Custom,
  all editable in Settings.
- CLI: `tt classroom open <resource> --label "..."`, `list`, `diff`,
  `promote`, `reopen`.
- Widget kit grew four generic pieces for this and future tools:
  `ResourcePicker` (from the library or a dialog), `TextField`,
  `ActionTable` (rows with action buttons, refreshable) and `TextView`.
  `RunResult.texts` and the optional `SupportsActions.act(name, row, ctx)`
  plugin method back them.

### Phase 1a — Resource Library (2026-10-06)

- `core/library/`: scanner with kind classification and hidden-cruft rules,
  text extraction for .py/.txt/.md/.csv/.pdf only (pypdf, 20-page cap),
  iCloud placeholders (`.name.icloud` stubs and EDEADLK reads) marked
  cloud-only instead of failing the run, SQLite + FTS5 index at
  `~/.config/teaching-tools/library.db` with incremental re-index by
  mtime/size, tags and notes in `<root>/.teaching-tools/tags.json`.
- `LibraryService` / `ResourceService`: `search`, `open_externally` (macOS
  `open`), `reveal`, `pick` (shell dialog), `open_for_class` stub for 1b.
  Plugins get it as `ctx.resources`.
- CLI: `tt library index [--full]`, `search <q> [--kind] [--tag] [--hidden]`,
  `tags <path> [--set] [--notes]`, `status`.
- Shell: sidebar Tools | Resources switch; Resources shows a search box,
  type filter, hidden toggle and a folder tree built from the index. Main
  area shows search results with snippets beside a preview pane: Python with
  syntax highlighting, plain text/markdown/CSV, images, first-page PDF text,
  and an open-externally card for Office, Scratch, media and everything
  else. Tag editor underneath. Re-index runs in a worker with progress; an
  empty index is built automatically on first launch.
- Settings: resources folder picker (changing it triggers a full re-index).
- Full index of the real root (587 files): 3.3 s; incremental: 0.0 s.
- Fixed: one SQLite commit per file made indexing take minutes; the stderr
  log handler broke under typer's CliRunner; table previews no longer
  stretch their last column.

### Phase 0 — Skeleton (2026-10-06)

- uv-managed src layout; `tt` (typer) and `tt-gui` (PySide6) entry points.
- `core/`: `Table`, CSV/XLSX I/O with fake-data marker, TOML config, paths,
  logging, `ToolPlugin` protocol, declarative panel spec, pkgutil discovery,
  `tt new` scaffolder.
- `core/privacy.py`: identifier columns (name, id, upn, candidate, email,
  class and variants) are dropped on every table load; no tool can opt out.
- `shell/`: launcher with sidebar, stacked panels, settings page, log drawer,
  dark/light theme, shared widget kit (path picker, table preview, editable
  table, options form, run bar, image view, results area).
- `tools/hello`: reference tool, reads an anonymous marks file (q1..qn) and
  adds a Total column.
- Guard rails: import-linter contracts, boundary tests, pre-commit hook
  refusing CSV/XLSX files without `# FAKE DATA`.
