#!/usr/bin/env bash
# Run the T2/T3 lanes to the end across usage-limit resets (paper/SPEC.md decisions 2026-11-20; deviations §19).
# Re-runs harness/run_t2_t3_lanes.sh (each arm resumes where it stopped) and acts on its exit code:
#   0  every lane done                       -> stop, exit 0
#   75 a lane stopped on a usage limit / API failure (run_arm.py EXIT_LIMIT)
#        every account limited  -> wait until the earliest is free (harness/tokens.py next-free) + MARGIN_S
#        an account still free   -> API failure, not a limit: wait RETRY_S
#   else broken (version pin, setup, preflight, PMxAgent stack down, crash) -> stop with that code; needs a human
# Start it from a Terminal tab, never from inside a Claude session (it refuses), one copy at a time (lock):
#   caffeinate -is bash harness/resume_lanes.sh 2>&1 | tee -a logs/t2t3_resume.log
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
MAX_ROUNDS=${RESUME_MAX_ROUNDS:-30}   # usage-limit windows to sit out before giving up
MARGIN_S=${RESUME_MARGIN_S:-300}      # after the reported reset
RETRY_S=${RESUME_RETRY_S:-1800}       # after an API failure while an account is free
POLL_S=${RESUME_POLL_S:-60}           # (RESUME_* overrides exist for harness/tests only)
export T3B_OK=1       # S2 passed (#4, logs/deviations.md §18)

if [ -n "${CLAUDECODE:-}" ] || [ -n "${CLAUDE_CODE_ENTRYPOINT:-}" ]; then
  echo "refusing to run inside a Claude Code session: start it from a Terminal tab (deviations §19)" >&2; exit 2
fi
LOCK="$REPO/logs/.resume_lanes.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  old=$(cat "$LOCK/pid" 2>/dev/null || true)
  if [ -n "$old" ] && kill -0 "$old" 2>/dev/null; then
    echo "another resume_lanes.sh is running (pid $old): at most 2 sessions in total (deviations §3)" >&2; exit 2
  fi
  echo "removing stale lock of pid ${old:-?}"
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT

now() { date +%s; }
next_free() {   # epoch when a pool account is next free; now if one is
  local t; t=$(python3 harness/tokens.py next-free) || t=0
  case "$t" in ''|*[!0-9]*) now ;; *) echo "$t" ;; esac
}

for round in $(seq 1 "$MAX_ROUNDS"); do
  echo "[round $round] starting lanes $(date)"; python3 harness/tokens.py status
  bash harness/run_t2_t3_lanes.sh; rc=$?
  echo "[round $round] lanes exit $rc at $(date)"
  case "$rc" in
    0)  echo "all lanes done $(date)"; exit 0 ;;
    75) ;;
    *)  echo "lanes broken (exit $rc): not a usage limit - fix and start again" >&2; exit "$rc" ;;
  esac
  free=$(next_free)
  if [ "$free" -gt "$(now)" ]; then
    until_t=$(( free + MARGIN_S )); echo "[round $round] every account limited; resuming at $(date -r "$until_t")"
    # re-read the pool each minute: a token added meanwhile, or an earlier reset, brings the restart forward
    while [ "$(now)" -lt "$until_t" ]; do
      sleep "$POLL_S"; f=$(next_free)
      [ $(( f + MARGIN_S )) -lt "$until_t" ] && until_t=$(( f + MARGIN_S ))
    done
  else
    echo "[round $round] stopped although an account is free (API failure?): retrying in $(( RETRY_S / 60 )) min"
    sleep "$RETRY_S"
  fi
done
echo "gave up after $MAX_ROUNDS rounds $(date)" >&2; exit 1
