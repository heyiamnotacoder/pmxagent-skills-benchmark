#!/usr/bin/env python3
"""Per arm x task summary of accuracy and token usage -> results/summary.md (+ results/summary.csv).

Tokens are summed per model from the ledger's model_usage_json (includes any internal helper-model calls).
cost_usd = Claude Code's own list-price estimate (costBasis=list); runs used a subscription, so this is notional.
"""
import csv, json, os, statistics as st
from collections import defaultdict

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


def main():
    runs = [r for r in csv.DictReader(open(os.path.join(RES, "runs.csv"))) if r["rep"] != "0"]
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
               "n_ok": sum(r["status"] == "ok" and r["is_error"] != "True" for r in rs),
               "accuracy_overall": ms(acc), "accuracy_min": min([a for a in acc if a is not None], default=""),
               "n_distinct_outputs": "",
               "cost_usd_per_run": ms([f(r["cost_usd"]) for r in rs], 3),
               "cost_usd_total": round(sum(f(r["cost_usd"]) or 0 for r in rs), 3),
               "wall_min_per_run": ms([f(r["duration_s"]) / 60 for r in rs], 1),
               "turns_per_run": ms([f(r["num_turns"]) for r in rs], 1),
               "tool_calls_per_run": ms([f(r["tool_calls"]) for r in rs], 1),
               "tool_errors_per_run": ms([f(r["tool_errors"]) for r in rs], 1),
               "tokens_by_model": json.dumps({m: dict(v) for m, v in tok.items()}, separators=(",", ":"))}
        hashes = set()
        for r in rs:
            p = os.path.join(RES, "raw", arm, task, r["runid"], "output_sha256.json")
            if os.path.exists(p):
                hashes.add(json.dumps(json.load(open(p)), sort_keys=True))
        row["n_distinct_outputs"] = len(hashes)
        if task == "T2_case":
            row["t2_completed"] = sum(s.get("completed") == "True" for s in sc)
            row["t2_summary_consistent_pct"] = ms([f(s.get("summary_consistent_pct")) for s in sc], 1)
            row["t2_ec50"] = ms([f(s.get("ec50")) for s in sc], 1)
        rows.append(row)
    cols = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    with open(os.path.join(RES, "summary.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader(); w.writerows(rows)
    show = ["arm", "task", "model", "n_runs", "n_ok", "accuracy_overall", "accuracy_min", "n_distinct_outputs",
            "cost_usd_per_run", "wall_min_per_run", "turns_per_run", "tool_calls_per_run", "tool_errors_per_run"]
    md = ["# Benchmark summary", "", "accuracy = paper metric (% of subject-parameters within 1% of PKanalix; mean of 7) "
          "for NCA tasks; % of 3 typical values within 1% of analytical truth for T3d; T2 see columns in summary.csv.",
          "cost_usd = Claude Code list-price estimate from token usage (runs used a subscription).", "",
          "| " + " | ".join(show) + " |", "|" + "---|" * len(show)]
    md += ["| " + " | ".join(str(r.get(c, "")) for c in show) + " |" for r in rows]
    md += ["", "## Tokens by model (summed over runs)", "", "| arm | task | tokens |", "|---|---|---|"]
    md += [f"| {r['arm']} | {r['task']} | `{r['tokens_by_model']}` |" for r in rows]
    open(os.path.join(RES, "summary.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
