#!/usr/bin/env bash
# T2 case study, at most 2 concurrent Claude Code sessions (as T1, logs/deviations.md §3):
#   lane 1 = A1 (PMxAgent; waits until the stack answers), lane 2 = A0, A2, A3, A4 one after another.
# --until tops each arm up to the target number of valid reps and stops a lane on a usage-limit (429) response.
cd "$(dirname "$0")/.."
S=claude-sonnet-4-6; H=claude-haiku-4-5-20251001
mkdir -p logs
( until curl -sf -o /dev/null http://localhost:5762/__docs__/; do sleep 30; done
  python3 harness/run_arm.py run A1 T2_case 3 $S --until ) >> logs/t2_lane_A1.log 2>&1 &
( for a in A0 A2 A3; do python3 harness/run_arm.py run $a T2_case 10 $S --until || exit 1; done
  python3 harness/run_arm.py run A4 T2_case 10 $H --until ) >> logs/t2_lane_others.log 2>&1 &
wait
echo "T2 lanes finished $(date)"
