# Using the launcher

The window has two sidebar roots: **Tools** and **Resources**.

Pick a tool, fill in its panel top to bottom, press the big button. Results
appear below the inputs and files are written to the output folder, which the
run bar names before you press Run: next to the input by default,
`~/TeachingSessions/outputs/<tool>/` for tools with no input file, or
wherever Settings says. **Open output folder** works before and after the
run. The log at the bottom of each panel says exactly what happened.

## Shortcuts

| Keys | Does |
| --- | --- |
| ⌘K | Jump to the Resources search box |
| ⌘O | Classroom with the library picker open |
| ⌘1 – ⌘9 | Switch tool |
| ⌘L | Show or hide the log drawer |
| ⌘, | Settings |

## Settings

| Setting | Meaning |
| --- | --- |
| Theme | dark or light |
| Output folder | where tools write; empty means next to the input, or `<sessions folder>/outputs/<tool>` when there is none |
| Resources folder | what the Resource Library indexes (read-only to every tool) |
| Sessions folder | where Classroom puts lesson copies; local by default |
| Editor | Thonny, IDLE, system default, or a custom `{file}` command |
| Exam board | OCR J277 or AQA 8525: sets default presets and tags |
| Header / footer text | printed on every worksheet and key |

Everything is saved to `~/.config/staffroom/config.toml` as you change it.

## The command line

Every tool is also a `staff` subcommand with the same options. `staff --help`
lists them; `staff <tool> --help` shows a tool's commands. The CLI is the
primary way the tools are tested, so if something works in the panel it
works in the terminal and vice versa.
