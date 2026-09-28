#!/usr/bin/env bash
# Full benchmark matrix. One background process per arm (arms in parallel, runs within an arm sequential).
# Each run = headless Claude Code subagent in a fresh git worktree (harness/run_arm.py).
#   A0/A1/A2/A3: claude-sonnet-4-6   A4: claude-haiku-4-5-20251001
# T1 x10 (A1 x3: published 10-run outputs exist), T2 x10, T3a-e x5.
set -u
cd "$(dirname "$0")/.."
SONNET=claude-sonnet-4-6; HAIKU=claude-haiku-4-5-20251001
mkdir -p logs
arm_seq() {
  local arm=$1 model=$2 t1=$3
  python3 harness/run_arm.py run "$arm" T1_nca "$t1" "$model"
  python3 harness/run_arm.py run "$arm" T2_case 10 "$model"
  for t in T3a_messy T3b_blq T3c_units T3d_oral T3e_large; do
    python3 harness/run_arm.py run "$arm" "$t" 5 "$model"
  done
}
for spec in "A0 $SONNET 10" "A1 $SONNET 3" "A2 $SONNET 10" "A3 $SONNET 10" "A4 $HAIKU 10"; do
  set -- $spec
  arm_seq "$1" "$2" "$3" > "logs/matrix_$1.log" 2>&1 &
done
wait
echo "matrix done $(date)"
