"""Which ledger rows (results/runs.csv) count as valid runs: the one rule the harness (--until) and scoring share.

A run is valid if it completed (status ok, no error) or failed by the arm itself (crash / timeout / error after real
work, deviations §22), and is not listed in results/exclusions.csv. Usage-limit (HTTP 429) stops and infrastructure
failures (API/auth error, no work done) are not valid and are re-run. Exclusions are
decided from how a run was set up, never from its accuracy (CLAUDE.md, logs/deviations.md); each row names the
deviation that explains it. The ledger itself is append-only and is never rewritten. Stdlib only.
"""
import csv, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "results", "runs.csv")
EXCLUSIONS = os.path.join(ROOT, "results", "exclusions.csv")


def completed(r):
    """The run finished normally: not cut off by a usage limit, a crash or a timeout (deviations §1)."""
    return r["status"] == "ok" and r["is_error"] != "True"


def rate_limited(r):
    """A usage-limit (HTTP 429) stop, mid-run or instant (deviations §1, §14, §21)."""
    return str(r.get("status", "")).startswith("failed_ratelimit")


def _did_work(r):
    """The agent used tokens or tools before the rep ended (a timeout leaves no cost: Claude Code never reported)."""
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):   # "", None, "None"
            return 0.0
    return num(r.get("cost_usd")) > 0 or num(r.get("tool_calls")) > 0


def arm_failure(r):
    """The agent did real work, then crashed, hit the time limit or ended in error, with no API/auth error behind it.
    That is the arm's own failure: it counts as a run, scored on whatever it left (no scorable output -> 0;
    deviations §22, SPEC.md "Pre-specified analysis")."""
    if completed(r) or rate_limited(r) or str(r.get("api_error_status") or "") not in ("", "None"):
        return False
    s = str(r.get("status", ""))
    return (s == "timeout" or s.startswith("exit") or s == "ok") and _did_work(r)


def infra_failure(r):
    """Ended outside the arm's control and not by a usage limit: an API/auth error, no work done, or a status the
    harness gave for its own bug (e.g. preflight_bug_*). Not counted; --until re-runs it (deviations §22)."""
    return not completed(r) and not rate_limited(r) and not arm_failure(r)


def exclusions(path=EXCLUSIONS):
    """Run IDs excluded for a protocol reason (columns runid, reason, deviation); none if the file is absent."""
    if not os.path.exists(path):
        return frozenset()
    with open(path, newline="") as f:
        return frozenset(r["runid"] for r in csv.DictReader(f) if r.get("runid"))


def valid(r, excluded):
    """Counts toward --until targets and is scored: completed, or failed by the arm itself (§22); never excluded."""
    return (completed(r) or arm_failure(r)) and r.get("runid") not in excluded
