#!/usr/bin/env bash
# T2 (x10) and T3a-e (x5) for all arms, at most 2 concurrent Claude Code sessions (as for T1, logs/deviations.md §3):
#   lane 1 = A1 (PMxAgent; needs `bash harness/pmxagent.sh up`), lane 2 = A0, A2, A3 (Sonnet), then A4 (Haiku).
# --until tops each arm x task up to the target number of valid reps and stops a lane on a usage-limit (429)
# response, so re-running this script after the limit resets resumes where it stopped.
#
# T3b runs only after the BLQ protocol check (scoring/check_blq_reference.py, paper/PLAN.md R1):
#   T3B_OK=1 bash harness/run_t2_t3_lanes.sh
# Optional R0 (A1 T1 top-up to 10 runs): A1_T1=10 bash harness/run_t2_t3_lanes.sh
set -u
cd "$(dirname "$0")/.."
S=claude-sonnet-4-6; H=claude-haiku-4-5-20251001
TASKS="T3d_oral:5 T2_case:10 T3a_messy:5 T3c_units:5 T3e_large:5"
[ "${T3B_OK:-0}" = 1 ] && TASKS="$TASKS T3b_blq:5" || echo "T3b skipped (set T3B_OK=1 after the BLQ check)"
mkdir -p logs

lane() {   # lane <model> <arm>...
  local model=$1; shift
  for arm in "$@"; do
    for spec in $TASKS; do
      python3 harness/run_arm.py run "$arm" "${spec%%:*}" "${spec##*:}" "$model" --until || return 1
    done
  done
}

for arm in A0 A1 A2 A3 A4; do python3 harness/run_arm.py setup "$arm" || exit 1; done
( [ -n "${A1_T1:-}" ] && python3 harness/run_arm.py run A1 T1_nca "$A1_T1" $S --until
  lane $S A1 ) >> logs/t2t3_lane_A1.log 2>&1 &
( lane $S A0 A2 A3 && lane $H A4 ) >> logs/t2t3_lane_others.log 2>&1 &
wait
echo "T2/T3 lanes finished $(date) - next: python3 scoring/score_all.py && python3 scoring/summarize.py && python3 scoring/stats.py"
