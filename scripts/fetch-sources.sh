#!/usr/bin/env bash
# Fetch the repository-style witness sources that verify-witness.py cannot
# download by itself (it auto-fetches http(s) witness.source URLs, but creeds
# and hymns cite git repos and multi-file editions). Idempotent; shallow.
#
#   bash scripts/fetch-sources.sh [SOURCES_DIR]      # default: ./sources
#
# The commentary index sources (Commentaries-Database, Treasury of David,
# Matthew Henry, Calvin) are only needed to *generate* new entries, not to
# verify shipped ones, so they are not fetched here; see docs/SOURCES.md.
set -euo pipefail
S="${1:-$(cd "$(dirname "$0")/.." && pwd)/sources}"
mkdir -p "$S/gutenberg" "$S/ccel/wesley"

clone() { # repo-url dir
  if [ -d "$S/$2/.git" ]; then git -C "$S/$2" pull -q --ff-only || true
  else git clone -q --depth 1 "$1" "$S/$2"; fi
}
get() { # url dest
  [ -s "$2" ] || curl -fsSL --retry 3 -A "while-you-wait fetch-sources" -o "$2" "$1"
}

clone https://github.com/NonlinearFruit/Creeds.json Creeds.json
clone https://github.com/mzealey/openhymnal openhymnal

for n in 13341 4272 30362 26874 31647; do
  get "https://www.gutenberg.org/cache/epub/$n/pg$n.txt" "$S/gutenberg/pg$n.txt"
done
get "https://ccel.org/ccel/n/newton/olneyhymns/cache/olneyhymns.txt" "$S/ccel/newton-olneyhymns.txt"

# Charles Wesley, 1780 Collection (CCEL): index page plus the hymn pages the corpus cites.
get "https://ccel.org/w/wesley/hymn/jw.html" "$S/ccel/wesley/jw.html"
for h in 0001 0002 0028 0051 0066 0140 0143 0147 0168 0190 0194 0201 0209 0266 0318 0324 0343 0385 0531 0683 0688 0726 0729 0738 0784 0859; do
  get "https://ccel.org/w/wesley/hymn/jwg${h:0:2}/jwg$h.html" "$S/ccel/wesley/jwg$h.html"
done
echo "sources ready under $S"
