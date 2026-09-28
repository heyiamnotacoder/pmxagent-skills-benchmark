#!/usr/bin/env bash
# T1 only, at most 2 concurrent Claude Code sessions: lane 1 = A1 (PMxAgent), lane 2 = A0, A2, A3, A4 one after another.
# --until: tops each arm up to the target number of valid reps; stops a lane on a usage-limit (429) response.
cd "$(dirname "$0")/.."
S=claude-sonnet-4-6; H=claude-haiku-4-5-20251001
( python3 harness/run_arm.py run A1 T1_nca 3 $S --until ) >> logs/t1_lane_A1.log 2>&1 &
( for a in A0 A2 A3; do python3 harness/run_arm.py run $a T1_nca 10 $S --until || exit 1; done
  python3 harness/run_arm.py run A4 T1_nca 10 $H --until ) >> logs/t1_lane_others.log 2>&1 &
wait
echo "T1 lanes finished $(date)"
