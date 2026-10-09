#!/usr/bin/env bash
# Regenerate every screenshot referenced from docs/**/*.md, offscreen and
# reproducibly. `just screenshots` runs this.
#
# Nothing here touches the owner's config or resources: STAFFROOM_HOME is a
# throwaway folder created for this run, its config points at the invented
# fixture root in scripts/screenshots/resources/, and tool outputs go to
# folders that die with the process (the launcher does that in --screenshot
# mode; the two CLI renders below use a scratch folder under the same home).
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

home="$(mktemp -d -t staffroom-shots)"
trap 'rm -rf "$home"' EXIT
export STAFFROOM_HOME="$home"
export QT_QPA_PLATFORM=offscreen
# Qt's offscreen platform has no system theme; keep the window size fixed too.
size="1240x780"

fixtures="$root/scripts/screenshots/resources"
mkdir -p "$home/sessions" "$home/out"
cat > "$home/config.toml" <<TOML
[general]
theme = "dark"
resources_root = '$fixtures'
sessions_root = '$home/sessions'
board = "ocr"

[tools]
TOML

# Index the fixture root up front so the Resources screenshots do not race the
# first-index worker and the name-only banner is already there.
uv run staff library index >/dev/null

shot() {
    local name="$1"; shift
    uv run staffroom --size "$size" "$@" --screenshot "docs/$name.png"
}

# Launcher and the first-run card
shot launcher-dark  --tool marks --open examples/marks_10x.csv --run --theme dark
shot first-run-dark --first-run --theme dark
shot settings       --settings --theme dark

# Tool panels, in sidebar order
shot classroom-dark            --tool classroom --open "$fixtures/Python/Year 9/average.py" --theme dark
shot marks-dark                --tool marks --open examples/marks_10x_max.csv --run --theme dark
shot marks-warnings-light      --tool marks --open examples/marks_messy.csv --run --theme light
shot worksheet-light           --tool worksheet --run --theme light
shot parsons-dark              --tool parsons --open examples/year9.py --run --theme dark
shot quiz-light                --tool quiz --open examples/question_bank.md --run --theme light
shot trace-dark                --tool trace --open examples/year9.py --run --theme dark
shot trace-preset-dark         --tool trace --open examples/year9.py --preset "Year 9" --theme dark --size 1240x1500
shot trace-missing-input-dark  --tool trace --open "$fixtures/Python/Year 10/temperature.py" --run --theme dark
shot bugs-light                --tool bugs --open examples/year9.py --run --theme light
shot pseudocode-dark           --tool pseudocode --open examples/year9.py --run --theme dark

# Resource Library
shot library-python-dark --resource "Python/Year 9/average.py" --theme dark
shot library-name-only   --resource "Admin/mock_cover_sheet.txt" --theme dark

# Rendered files: the marks chart and one worksheet page
uv run staff marks run examples/marks_10x_max.csv --out "$home/out/marks" >/dev/null
cp "$home/out/marks/marks_10x_max_distribution.png" docs/marks-chart.png
echo "saved docs/marks-chart.png"

uv run staff worksheet make --topic truth_tables --difficulty hard --board ocr --seed 1 \
    --format pdf --out "$home/out/worksheet" --no-preview >/dev/null
sheet="$(ls "$home/out/worksheet"/*.pdf | grep -v -i key | head -1)"
if command -v pdftoppm >/dev/null; then
    pdftoppm -png -r 110 -f 1 -l 1 -singlefile "$sheet" docs/worksheet-sample
else
    # macOS fallback (lower resolution): `brew install poppler` for pdftoppm.
    sips -s format png "$sheet" --out docs/worksheet-sample.png >/dev/null
fi
echo "saved docs/worksheet-sample.png"
