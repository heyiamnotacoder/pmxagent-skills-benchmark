#!/usr/bin/env bash
# Run every skill's testthat suite.
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
for d in "$root"/skills/*/tests; do
  echo "== $(basename "$(dirname "$d")")"
  (cd "$d" && R_MAKEVARS_USER="$root/skills/pmx-library/scripts/Makevars.rxode2" Rscript -e 'r <- testthat::test_dir(".", reporter="summary", stop_on_failure=TRUE)')
done
