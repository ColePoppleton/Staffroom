# Staffroom task runner. `just` with no arguments lists these.

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

# Run a CLI command, e.g. `just run hello run examples/marks_10x.csv`
run *ARGS:
    uv run staff {{ARGS}}

# Open the launcher
gui *ARGS:
    uv run staffroom {{ARGS}}

# Scaffold a new tool: `just new marks`
new NAME:
    uv run staff new {{NAME}}

# Render the launcher (hello panel, example loaded, run) to docs/ in both themes
screenshots:
    QT_QPA_PLATFORM=offscreen uv run staffroom --tool hello --open examples/marks_10x.csv --run --theme dark --screenshot docs/launcher-dark.png
    QT_QPA_PLATFORM=offscreen uv run staffroom --tool hello --open examples/marks_10x.csv --run --theme light --screenshot docs/launcher-light.png

# Build the thin launcher app (runs this checkout via uv; updates need no reinstall)
app:
    uv run python packaging/make_launcher.py

# Build the thin launcher app and install it into /Applications
install:
    uv run python packaging/make_launcher.py --install

# Build a frozen, self-contained bundle with PyInstaller (for a machine without the repo)
bundle:
    uv run pyinstaller packaging/staffroom.spec --noconfirm --clean

# Pull the latest code and sync dependencies (what the app's Update button does)
update:
    uv run staff update

# Redraw the app icon from scripts/make_icon.py
icon:
    uv run python scripts/make_icon.py

# Cut a release from main: bump (patch|minor|major), move Unreleased in CHANGELOG, commit, tag, push.
# The tag triggers the Release workflow (wheel + sdist + GitHub Release with the notes).
release PART="patch":
    @git diff --quiet || (echo "commit or stash changes first" && exit 1)
    @[ "$(git branch --show-current)" = "main" ] || (echo "release from main (merge dev first)" && exit 1)
    uv run python scripts/release.py bump {{PART}}
    uv lock --quiet
    uv run python scripts/release.py tag
    git push --follow-tags
    @echo "pushed; watch the Release workflow on GitHub"

# Serve the documentation site locally
docs:
    cp CHANGELOG.md docs/changelog.md
    uv run --only-group docs mkdocs serve

# Everything CI would do
check: lint test
