#!/usr/bin/env bash
# Build the bioRxiv submission PDF (paper/SPEC.md slice S14, issue #16).
# Regenerates stats, figures (incl. Fig 1) and tables from results/, builds paper/main.pdf, then refuses it
# (exit 1) if main.tex has a \TODO, line numbers are off, a figure is missing, or the log has undefined references.
# Usage: bash paper/make_biorxiv.sh
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

# Reproducible PDFs: matplotlib and pdfTeX stamp this date (the last results commit) instead of the clock, so
# rebuilding from the same results gives byte-identical figures.
export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct -- results)" FORCE_SOURCE_DATE=1

python3 scoring/stats.py
python3 scoring/figures.py
(cd paper/figures && latexmk -pdf -interaction=nonstopmode -halt-on-error -g fig_arch.tex >/dev/null)
python3 paper/tables.py
(cd paper && latexmk -pdf -interaction=nonstopmode -halt-on-error -g main.tex >/dev/null) \
  || { echo "LaTeX failed; see paper/main.log" >&2; exit 1; }

python3 paper/check_biorxiv.py paper

# Regenerated outputs should match what is committed; a difference means the committed tables/figures were stale.
changed="$(git status --porcelain -- paper/tables paper/figures results/stats.* results/stats_secondary.csv)"
if [ -n "$changed" ]; then
  echo "WARNING: regenerated files differ from the commit; review and commit them before posting:" >&2
  echo "$changed" >&2
fi
echo "PDF: $root/paper/main.pdf ($(pdfinfo paper/main.pdf 2>/dev/null | awk '/^Pages:/{print $2}') pages)"
