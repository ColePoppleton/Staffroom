#!/usr/bin/env bash
# Regenerate every screenshot referenced from docs/**/*.md, offscreen and
# reproducibly. `just screenshots` runs this.
#
# Nothing here touches the owner's config or resources: STAFFROOM_HOME is a
# throwaway folder created for this run, its config points at the invented
# fixture root in scripts/screenshots/resources/, and tool outputs go to
# folders that die with the process (the launcher does that in --screenshot
# mode; the two CLI renders below use a scratch folder under the same home).
#
# Every sheet prints a date in its header. STAFFROOM_DATE pins it (read in
# core/export/dating.py), so the renders are the same bytes whichever day they
# are made and a re-run only changes the images whose content changed. Keep it
# at the day the committed renders show; a teacher's own runs never set it and
# print today's date.
#
# The launcher shots also pass `--today` with the same day, so the Classroom
# run bar's "Copies to …/sessions/<day>" is pinned too (#116). That is a
# separate, screenshot-only flag on purpose: STAFFROOM_DATE never decides
# where a lesson copy goes, and `--today` only changes what the run bar says
# (the launcher refuses it without --screenshot; a run still copies into
# today's folder).
#
#   scripts/screenshots.sh           every screenshot (what `just screenshots` runs)
#   scripts/screenshots.sh outputs   only the rendered files ("Rendered files" below)
set -euo pipefail

only="${1:-all}"
case "$only" in
    all | outputs) ;;
    *) echo "usage: $0 [outputs]" >&2; exit 2 ;;
esac
export STAFFROOM_DATE="${STAFFROOM_DATE:-2026-10-09}"

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

if [[ "$only" == all ]]; then

# Index the fixture root up front so the Resources screenshots do not race the
# first-index worker and the name-only banner is already there.
uv run staff library index >/dev/null

shot() {
    local name="$1"; shift
    uv run staffroom --size "$size" --today "$STAFFROOM_DATE" "$@" --screenshot "docs/$name.png"
}

# Launcher and the first-run card
shot launcher-dark  --tool marks --open examples/marks_10x.csv --run --theme dark
shot first-run-dark --first-run --theme dark
shot settings       --settings --theme dark

# The sidebar footer (version and update state) in both themes, cropped from
# a full launcher render so it always matches the real window.
footer() {
    local theme="$1"
    uv run staffroom --size "$size" --today "$STAFFROOM_DATE" --tool marks --theme "$theme" \
        --screenshot "$home/launcher-$theme.png" >/dev/null
    uv run python - "$home/launcher-$theme.png" "docs/sidebar-footer-$theme.png" "${size%x*}" <<'PY'
import sys
from PIL import Image

from staffroom.shell.sidebar import SIDEBAR_WIDTH

image = Image.open(sys.argv[1])
scale = image.width / int(sys.argv[3])  # the device pixel ratio of the render
bottom = image.height
image.crop((0, bottom - round(48 * scale), round(SIDEBAR_WIDTH * scale), bottom)).save(sys.argv[2])
print("saved", sys.argv[2])
PY
}
footer dark
footer light

# Tool panels
shot classroom-dark            --tool classroom --open "$fixtures/Python/Year 9/average.py" --theme dark
shot marks-dark                --tool marks --open examples/marks_10x_max.csv --run --theme dark
shot marks-warnings-light      --tool marks --open examples/marks_messy.csv --run --expand --theme light
shot worksheet-light           --tool worksheet --run --theme light
shot parsons-dark              --tool parsons --open examples/year9.py --run --theme dark
shot quiz-light                --tool quiz --open examples/question_bank.md --option topics=binary,cpu,loops --option count=8 --run --theme light
shot trace-dark                --tool trace --open examples/year9.py --run --select-row 8 --theme dark
shot trace-preset-dark         --tool trace --open examples/year9.py --preset "Year 9" --theme dark --size 1240x1500
shot trace-missing-input-dark  --tool trace --open "$fixtures/Python/Year 10/temperature.py" --run --theme dark
shot bugs-light                --tool bugs --open examples/year9.py --run --select-row 1 --theme light
shot pseudocode-dark           --tool pseudocode --open examples/year9.py --run --theme dark

# Resource Library
shot library-python-dark --resource "Python/Year 9/average.py" --theme dark
shot library-name-only   --resource "Admin/mock_cover_sheet.txt" --theme dark

fi  # end of the launcher screenshots

# Rendered files: the marks chart and one worksheet page
uv run staff marks run examples/marks_10x_max.csv --out "$home/out/marks" >/dev/null
cp "$home/out/marks/marks_10x_max_distribution.png" docs/marks-chart.png
echo "saved docs/marks-chart.png"

# The pages the tools print, for the home page's fan and its "What comes out"
# gallery: page 1 of each PDF, made from the example files by the same
# commands a teacher would type. The date in each page's header is
# STAFFROOM_DATE (set at the top), so these do not churn from day to day.
page() {
    local pdf="$1" name="$2" dpi="${3:-90}"
    if command -v pdftoppm >/dev/null; then
        pdftoppm -png -r "$dpi" -f 1 -l 1 -singlefile "$pdf" "docs/$name"
    else
        # macOS fallback (lower resolution): `brew install poppler` for pdftoppm.
        sips -s format png "$pdf" --out "docs/$name.png" >/dev/null
    fi
    echo "saved docs/$name.png"
}
first_pdf() { ls "$1"/*.pdf | grep -v -i key | head -1; }

uv run staff worksheet make --topic truth_tables --difficulty hard --board ocr --seed 1 \
    --format pdf --out "$home/out/worksheet" --no-preview >/dev/null
page "$(first_pdf "$home/out/worksheet")" worksheet-sample 110

uv run staff worksheet make --topic binary --difficulty medium --board ocr --seed 1 --count 8 \
    --format pdf --out "$home/out/binary" --no-preview >/dev/null
page "$(first_pdf "$home/out/binary")" output-worksheet

uv run staff parsons make examples/year9.py --seed 1 --format pdf \
    --out "$home/out/parsons" --no-preview >/dev/null
page "$(first_pdf "$home/out/parsons")" output-parsons

uv run staff trace make examples/year9.py --format pdf --out "$home/out/trace" --no-preview >/dev/null
page "$(first_pdf "$home/out/trace")" output-trace

uv run staff bugs make examples/year9.py --seed 1 --format pdf --out "$home/out/bugs" >/dev/null
page "$(first_pdf "$home/out/bugs")" output-bugs

uv run staff fade make examples/year9.py --format pdf --out "$home/out/fade" --no-preview >/dev/null
page "$(first_pdf "$home/out/fade")" output-fade

uv run staff quiz export --bank examples/question_bank.md --format donow --seed 1 \
    --out "$home/out/quiz" >/dev/null
page "$(first_pdf "$home/out/quiz")" output-quiz

# Pseudocode writes text, not a page: keep the translation itself.
uv run staff pseudocode to-ocr examples/year9.py 2>/dev/null > docs/output-pseudocode-ocr.txt
echo "saved docs/output-pseudocode-ocr.txt"
