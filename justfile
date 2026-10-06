# Teaching Tools task runner. `just` with no arguments lists these.

set shell := ["zsh", "-cu"]

default:
    @just --list

# Install the virtualenv, dev dependencies and the pre-commit hooks
setup:
    uv sync
    uv run pre-commit install

# Run the whole test suite (core, tools, and the Qt shell offscreen)
test *ARGS:
    QT_QPA_PLATFORM=offscreen uv run pytest {{ARGS}}

# Ruff, mypy and the import-boundary contracts
lint:
    uv run ruff check .
    uv run ruff format --check .
    uv run mypy
    uv run lint-imports

# Auto-fix what ruff can and format
fix:
    uv run ruff check --fix .
    uv run ruff format .

# Run a CLI command, e.g. `just run hello run examples/class_list.csv`
run *ARGS:
    uv run tt {{ARGS}}

# Open the launcher
gui *ARGS:
    uv run tt-gui {{ARGS}}

# Scaffold a new tool: `just new marks`
new NAME:
    uv run tt new {{NAME}}

# Render the launcher (hello panel, example loaded, run) to docs/ in both themes
screenshots:
    QT_QPA_PLATFORM=offscreen uv run tt-gui --tool hello --open examples/class_list.csv --run --theme dark --screenshot docs/launcher-dark.png
    QT_QPA_PLATFORM=offscreen uv run tt-gui --tool hello --open examples/class_list.csv --run --theme light --screenshot docs/launcher-light.png

# Everything CI would do
check: lint test
