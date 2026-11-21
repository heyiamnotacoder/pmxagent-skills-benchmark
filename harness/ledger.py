"""Which ledger rows (results/runs.csv) count as valid runs: the one rule the harness (--until) and scoring share.

A run is valid if it completed (status ok, no error) and is not listed in results/exclusions.csv. Exclusions are
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


def crash_or_timeout(r):
    """Non-completed run that was NOT a usage-limit stop (e.g. crash exit1 or timeout; deviations §21)."""
    return not completed(r) and not rate_limited(r)


def exclusions(path=EXCLUSIONS):
    """Run IDs excluded for a protocol reason (columns runid, reason, deviation); none if the file is absent."""
    if not os.path.exists(path):
        return frozenset()
    with open(path, newline="") as f:
        return frozenset(r["runid"] for r in csv.DictReader(f) if r.get("runid"))


def valid(r, excluded):
    """Counts toward --until targets and is scored."""
    return completed(r) and r.get("runid") not in excluded
