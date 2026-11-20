#!/usr/bin/env bash
# Re-run harness/run_t2_t3_lanes.sh (it resumes where each arm stopped) until a round ends without a usage-limit stop.
# When every pool account is limited, wait until the earliest one is free again (harness/tokens.py next-free) + 5 min.
# Start it from a Terminal tab, never from inside a Claude session (paper/SPEC.md 2026-11-20; deviations §19):
#   caffeinate -is bash harness/resume_lanes.sh [<start epoch>]  2>&1 | tee -a logs/t2t3_resume.log
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
export T3B_OK=1                       # S2 passed (#4, logs/deviations.md §18)
next=${1:-0}
for round in $(seq 1 12); do
  [ "$(date +%s)" -lt "$next" ] && echo "[round $round] waiting until $(date -r "$next") or until an account is free"
  # Re-read the pool each minute: a newly added tokens/acct<N>, or a reset passing, ends the wait early.
  while [ "$(date +%s)" -lt "$next" ] && [ "$(python3 harness/tokens.py next-free)" -gt "$(date +%s)" ]; do sleep 60; done
  sizes=$(for f in logs/t2t3_lane_A1.log logs/t2t3_lane_others.log logs/t2t3_resume.log; do
            if [ -f "$f" ]; then wc -c < "$f" | tr -d ' '; else echo 0; fi; done | paste -sd, -)
  echo "[round $round] starting lanes $(date)"; python3 harness/tokens.py status
  bash harness/run_t2_t3_lanes.sh
  echo "[round $round] lanes exited $? at $(date)"
  stopped=$(python3 -I - "$REPO" "$sizes" <<'EOF'
import os, sys
repo, sizes = sys.argv[1], [int(x) for x in sys.argv[2].split(",")]
n = 0   # "usage limit" lines written during this round only
for log, off in zip(("t2t3_lane_A1.log", "t2t3_lane_others.log", "t2t3_resume.log"), sizes):
    p = os.path.join(repo, "logs", log)
    if os.path.exists(p):
        with open(p, "rb") as f:
            f.seek(off)
            n += f.read().decode(errors="replace").count("usage limit")
print(n)
EOF
)
  if [ "$stopped" = 0 ]; then echo "[round $round] no usage-limit stop: lanes finished $(date)"; exit 0; fi
  free=$(python3 harness/tokens.py next-free); now=$(date +%s)
  if [ "$free" -gt "$now" ]; then next=$(( free + 300 )); echo "[round $round] all accounts limited; next free $(date -r "$free")"
  else next=$(( now + 1800 )); echo "[round $round] stopped but an account is free (API failure?); retry in 30 min"; fi
done
echo "gave up after 12 rounds $(date)"; exit 1
