#!/usr/bin/env bash
# bash harness/run_arm.sh <A0|A1|A2|A3|A4> <task> <reps> <model>   (see harness/run_arm.py)
set -euo pipefail
exec python3 "$(dirname "$0")/run_arm.py" run "$@"
