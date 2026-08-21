#!/usr/bin/env bash
# The READMEs reference the PNGs, because not every renderer that shows a
# plugin README will load an SVG. The SVGs stay the editable source.
set -euo pipefail

cd "$(dirname "$0")/../plugins/agent-conductor/docs"

if ! python3 -c "import cairosvg" 2>/dev/null; then
  echo "install the renderer first: pip3 install cairosvg" >&2
  exit 1
fi

for svg in *.svg; do
  python3 - "$svg" <<'PY'
import re, sys
import cairosvg

svg = sys.argv[1]
head = open(svg).read(400)
width = int(re.search(r'width="(\d+)"', head).group(1))
height = int(re.search(r'height="(\d+)"', head).group(1))
png = svg.replace(".svg", ".png")
cairosvg.svg2png(url=svg, write_to=png, output_width=width * 2, output_height=height * 2)
print(f"{png} {width * 2}x{height * 2}")
PY
done
