#!/usr/bin/env python3
"""Per arm x task summary of accuracy and token usage -> results/summary.md (+ results/summary.csv).

Tokens are summed per model from the ledger's model_usage_json (includes any internal helper-model calls).
cost_usd = Claude Code's own list-price estimate (costBasis=list); runs used a subscription, so this is notional.
"""
import csv, json, os, statistics as st, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runstore
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness"))
import ledger   # the valid-run rule shared with the harness (results/exclusions.csv)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
TOK = ["inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens"]


def ms(xs, nd=2):
    xs = [x for x in xs if x is not None]
    if not xs:
        return ""
    return f"{st.mean(xs):.{nd}f} ± {st.stdev(xs):.{nd}f}" if len(xs) > 1 else f"{xs[0]:.{nd}f}"


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


OUTCOME_COLS = ("n_invalid_excluded", "n_infra_failed", "n_protocol_excluded", "n_arm_failed")


def count_outcomes(allruns, excluded):
    """Per (arm, task) counts keyed by summary column. Checked in this order, first match wins:
    n_invalid_excluded (HTTP 429), n_infra_failed (API/auth error, no work, harness-bug status: re-run either way, even
    if also listed in exclusions.csv), n_protocol_excluded (completed run or arm failure in results/exclusions.csv),
    n_arm_failed (crash / timeout / error after real work: valid, part of n_runs; deviations §22)."""
    c = {k: defaultdict(int) for k in OUTCOME_COLS}
    for r in allruns:
        key = (r["arm"], r["task"])
        if ledger.rate_limited(r):
            c["n_invalid_excluded"][key] += 1
        elif ledger.infra_failure(r):
            c["n_infra_failed"][key] += 1
        elif r["runid"] in excluded:
            c["n_protocol_excluded"][key] += 1
        elif ledger.arm_failure(r):
            c["n_arm_failed"][key] += 1
    return c


def main():
    allruns = [r for r in csv.DictReader(open(os.path.join(RES, "runs.csv"))) if r["rep"] != "0"]
    excluded = ledger.exclusions()
    runs = [r for r in allruns if ledger.valid(r, excluded)]   # valid runs only
    c = count_outcomes(allruns, excluded)
    scores = {r["runid"]: r for r in csv.DictReader(open(os.path.join(RES, "scores.csv")))} \
        if os.path.exists(os.path.join(RES, "scores.csv")) else {}
    g = defaultdict(list)
    for r in runs:
        g[(r["arm"], r["task"])].append(r)
    rows = []
    for (arm, task), rs in sorted(g.items()):
        tok = defaultdict(lambda: defaultdict(int))
        for r in rs:
            for m, u in json.loads(r["model_usage_json"] or "{}").items():
                for k in TOK:
                    tok[m][k] += u.get(k) or 0
        sc = [scores.get(r["runid"], {}) for r in rs]
        acc = [f(s.get("overall")) for s in sc]
        row = {"arm": arm, "task": task, "model": rs[0]["model"], "n_runs": len(rs),
               **{col: c[col][(arm, task)] for col in ("n_arm_failed", "n_invalid_excluded", "n_infra_failed",
                                                        "n_protocol_excluded")},
               "accuracy_overall": ms(acc), "accuracy_min": min([a for a in acc if a is not None], default=""),
               "n_distinct_outputs": "",
               "cost_usd_per_run": ms([f(r["cost_usd"]) for r in rs], 3),
               "cost_usd_total": round(sum(f(r["cost_usd"]) or 0 for r in rs), 3),
               "wall_min_per_run": ms([f(r["duration_s"]) / 60 for r in rs], 1),
               "turns_per_run": ms([f(r["num_turns"]) for r in rs], 1),
               "tool_calls_per_run": ms([f(r["tool_calls"]) for r in rs], 1),
               "tool_errors_per_run": ms([f(r["tool_errors"]) for r in rs], 1),
               "tokens_by_model": json.dumps({m: dict(v) for m, v in tok.items()}, separators=(",", ":"))}
        hashes = [runstore.output_hashes(arm, task, r["runid"]) for r in rs]   # local raw, else evidence manifest
        row["n_distinct_outputs"] = len({json.dumps(h, sort_keys=True) for h in hashes if h})
        if task == "T2_case":
            row["t2_completed"] = sum(s.get("completed") == "True" for s in sc)
            row["t2_summary_consistent_pct"] = ms([f(s.get("summary_consistent_pct")) for s in sc], 1)   # primary
            row["t2_summary_consistent_any_rule_pct"] = ms([f(s.get("summary_consistent_any_rule_pct")) for s in sc], 1)
            row["t2_ec50"] = ms([f(s.get("ec50")) for s in sc], 1)
        rows.append(row)
    cols = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    with open(os.path.join(RES, "summary.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
    show = ["arm", "task", "model", "n_runs", "n_arm_failed", "n_invalid_excluded", "n_infra_failed",
            "n_protocol_excluded",
            "accuracy_overall", "accuracy_min", "n_distinct_outputs",
            "cost_usd_per_run", "wall_min_per_run", "turns_per_run", "tool_calls_per_run", "tool_errors_per_run"]
    md = ["# Benchmark summary", "", "accuracy = paper metric (% of subject-parameters within 1% of PKanalix; mean of 7) "
          "for NCA tasks; % of 3 typical values within 1% of analytical truth for T3d; T2 see columns in summary.csv.",
          "cost_usd = Claude Code list-price estimate from token usage (runs used a subscription).",
          "n_runs = valid runs only; n_arm_failed = of n_runs, runs where the agent crashed, timed out or ended in error "
          "after real work, scored on what it left (deviations §22; a killed timeout reports no cost or turns, so it is "
          "missing from those means); "
          "n_invalid_excluded = runs cut off by the subscription usage limit (HTTP 429), not scored; "
          "n_infra_failed = API/auth errors or runs that did no work, not scored and re-run (deviations §22); "
          "n_protocol_excluded = completed runs or arm failures listed in results/exclusions.csv (reason + deviation there), not scored.", "",
          "| " + " | ".join(show) + " |", "|" + "---|" * len(show)]
    md += ["| " + " | ".join(str(r.get(c, "")) for c in show) + " |" for r in rows]
    md += ["", "## Tokens by model (summed over runs)", "", "| arm | task | tokens |", "|---|---|---|"]
    md += [f"| {r['arm']} | {r['task']} | `{r['tokens_by_model']}` |" for r in rows]
    open(os.path.join(RES, "summary.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
