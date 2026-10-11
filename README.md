# Staffroom

**Small tools for secondary computing teachers, on your own Mac.** Make a seeded binary
worksheet with its key, a Parsons problem or a trace table from a program, a do-now from a
question bank, and see which questions a class found hardest in a mock. Everything prints in
one plain house style. No pupil names, ever.

![Staffroom open on the Marks report: grades for ten scripts, a grade chart and the questions to reteach first](docs/marks-dark.png)

<table>
<tr>
<td><a href="https://colepoppleton.github.io/Staffroom/tools/worksheet/"><img src="docs/output-worksheet.png" width="180" alt="A binary, denary and hexadecimal worksheet, seed 1"></a></td>
<td><a href="https://colepoppleton.github.io/Staffroom/tools/quiz/"><img src="docs/output-quiz.png" width="180" alt="A do-now sheet from the example question bank"></a></td>
<td><a href="https://colepoppleton.github.io/Staffroom/tools/parsons/"><img src="docs/output-parsons.png" width="180" alt="A Parsons problem made from a short program"></a></td>
<td><a href="https://colepoppleton.github.io/Staffroom/tools/trace/"><img src="docs/output-trace.png" width="180" alt="A blank trace table made from the same program"></a></td>
</tr>
<tr>
<td align="center">Worksheet</td>
<td align="center">Do-now</td>
<td align="center">Parsons problem</td>
<td align="center">Trace table</td>
</tr>
</table>

Real first pages, made from the example files in this repository. Each comes with its answer
key as a separate file, in PDF and Word.

## Install (macOS 14 or later)

Two lines in Terminal. The first installs [uv](https://docs.astral.sh/uv/), which fetches
everything else; skip it if you have uv, or open a new Terminal window after it.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install --python 3.12 git+https://github.com/ColePoppleton/Staffroom@main
```

Then type `staffroom` to open it. No GitHub account is needed. To update later, quit
Staffroom and run `uv tool upgrade staffroom`; Settings › Updates says when a new release is
out.
[Install guide](https://colepoppleton.github.io/Staffroom/guide/install/) ·
[What's new](https://github.com/ColePoppleton/Staffroom/releases)

## What it does with your data

Your settings, an index of the files (and their text) in your resources folder, run counts
per tool and a log of file paths are stored on this Mac only; there is no account and no
server, and the only network call asks GitHub which release is newest. A name, candidate
number or row of marks from a marks file is never stored: identifier columns are dropped on
load and only class-level aggregates are saved.
[Check it yourself](https://colepoppleton.github.io/Staffroom/guide/privacy/).

## The tools

- **Lessons:** [Library](https://colepoppleton.github.io/Staffroom/tools/library/) ·
  [Classroom](https://colepoppleton.github.io/Staffroom/tools/classroom/)
- **Sheets & quizzes:** [Worksheet](https://colepoppleton.github.io/Staffroom/tools/worksheet/) ·
  [Quiz](https://colepoppleton.github.io/Staffroom/tools/quiz/)
- **From a program:** [Parsons](https://colepoppleton.github.io/Staffroom/tools/parsons/) ·
  [Trace](https://colepoppleton.github.io/Staffroom/tools/trace/) ·
  [Bugs](https://colepoppleton.github.io/Staffroom/tools/bugs/) ·
  [Fade](https://colepoppleton.github.io/Staffroom/tools/fade/) ·
  [Pseudocode](https://colepoppleton.github.io/Staffroom/tools/pseudocode/)
- **After a test:** [Marks](https://colepoppleton.github.io/Staffroom/tools/marks/)

Every tool has a page in the [documentation](https://colepoppleton.github.io/Staffroom/).

## Contributing

Bug reports and ideas for tools are welcome:
[open an issue](https://github.com/ColePoppleton/Staffroom/issues/new/choose), and please
never attach a real marks file. To work on the code, read the
[contributing guide](https://colepoppleton.github.io/Staffroom/contributing/).

## Licence

Free and open source under the [MIT licence](LICENSE).
