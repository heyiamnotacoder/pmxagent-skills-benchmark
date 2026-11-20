#!/usr/bin/env python3
"""Pre-specified arm comparisons (paper/SPEC.md, "Pre-specified analysis") -> results/stats.md + results/stats.csv.

For each task with a run-level accuracy (`overall` in results/scores.csv) and each pre-specified pair (X - Y):
  - difference in mean accuracy, 95% percentile bootstrap CI (resample runs within each arm; B = 10,000; fixed seed)
  - two-sided permutation p-value (exact when the number of splits is <= 200,000, else 100,000 random splits)
  - equivalence vs the +/-1.0 percentage-point margin: "equivalent" only if the whole 95% CI lies inside the margin
Per arm: n, mean, SD, min, max, and the number of distinct parameter-value sets (needs results/raw/; else "n/a").
Sensitivity (pre-specified 2026-11-17, before A1 T1 runs 4-10; logs/deviations.md §15): for an arm whose runs in a
task used more than one isolation regime (ledger `claude_config`: empty/"user" = user instructions loaded, as in T1;
"isolated" = none), per-regime arm stats and every pair involving that arm recomputed on each regime alone.
Post-hoc sensitivity (decided 2026-11-20 after seeing T1 scores; logs/deviations.md §17; labelled post-hoc): in each
task where a completed run had no scorable individual file (scored 0 under the primary rule), per-arm stats and every
pair involving an arm that lost runs, recomputed without those runs -> results/stats_posthoc.csv.
Per-arm rows of both sensitivity analyses: results/stats_{sensitivity,posthoc}_arms.csv (read by paper/tables.py).
Valid runs only (scores.csv already holds only those). Stdlib only.  Usage: stats.py [--b 10000] [--seed 20261116]
"""
import argparse, csv, glob, hashlib, itertools, math, os, random, statistics as st, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_all
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
PAIRS = [("A2", "A1"), ("A3", "A1"), ("A3", "A2"), ("A4", "A3"), ("A0", "A3")]
MARGIN = 1.0
EXACT_MAX = 200_000


def mean(xs):
    return sum(xs) / len(xs)


def boot_ci(x, y, b, rng):
    d = []
    for _ in range(b):
        d.append(mean([rng.choice(x) for _ in x]) - mean([rng.choice(y) for _ in y]))
    d.sort()
    return d[int(0.025 * b)], d[int(math.ceil(0.975 * b)) - 1]


def perm_p(x, y, rng, n_mc=100_000):
    obs = abs(mean(x) - mean(y))
    pool, nx = x + y, len(x)
    tot = sum(pool)
    eps = 1e-9

    def stat(sx):
        return abs(sx / nx - (tot - sx) / (len(pool) - nx))

    if math.comb(len(pool), nx) <= EXACT_MAX:
        hits = n = 0
        for idx in itertools.combinations(range(len(pool)), nx):
            n += 1
            hits += stat(sum(pool[i] for i in idx)) >= obs - eps
        return hits / n, "exact"
    hits = 0
    for _ in range(n_mc):
        hits += stat(sum(rng.sample(pool, nx))) >= obs - eps
    return (hits + 1) / (n_mc + 1), "MC"


def value_set_hash(run_dir, scored_file):
    """Hash of the scored individual table: (subject, parameter, value at 6 significant digits), sorted."""
    p = os.path.join(run_dir, scored_file)
    if not scored_file or not os.path.exists(p):
        return None
    d = score_all.load_any(p)
    items = sorted((s, k, "nan" if math.isnan(v) else f"{v:.6g}") for (s, k), v in d.items())
    return hashlib.sha256(repr(items).encode()).hexdigest()


def regime(ledger_row):
    """Isolation regime of a run: T1-era runs have an empty `claude_config`, which meant user config loaded."""
    return (ledger_row.get("claude_config") or "user").strip() or "user"


def compare(x, y, b, rng):
    lo, hi = boot_ci(x, y, b, rng)
    p, how = perm_p(x, y, rng)
    return {"n_x": len(x), "n_y": len(y), "diff": mean(x) - mean(y), "ci_lo": lo, "ci_hi": hi, "p_perm": p,
            "p_method": how, "equivalent_1pp": -MARGIN < lo and hi < MARGIN}


def sensitivity(by, pairs, b, seed):
    """by[task][arm][regime] = accuracies. Only arms with >1 regime in a task are split."""
    arms, out = [], []
    for task in sorted(by):
        pooled = {arm: [v for vs in regs.values() for v in vs] for arm, regs in by[task].items()}
        for arm in sorted(by[task]):
            regs = by[task][arm]
            if len(regs) < 2:
                continue
            for reg in sorted(regs):
                x = regs[reg]
                arms.append({"task": task, "arm": arm, "regime": reg, "n": len(x), "mean": mean(x),
                             "sd": st.stdev(x) if len(x) > 1 else 0.0})
                for xa, ya in pairs:
                    if arm not in (xa, ya) or xa not in pooled or ya not in pooled:
                        continue
                    x_, y_ = (x if xa == arm else pooled[xa]), (x if ya == arm else pooled[ya])
                    rng = random.Random(f"{seed}-{task}-{xa}-{ya}-{arm}-{reg}")
                    out.append({"task": task, "comparison": f"{xa} - {ya}", "split_arm": arm, "regime": reg,
                                **compare(x_, y_, b, rng)})
    return arms, out


def posthoc_unscorable(rows, pairs, b, seed):
    """rows: scores.csv dicts. Returns (arm stats, pair comparisons) without runs noted UNSCORABLE, only for tasks
    where at least one such run exists, and only pairs involving an arm that lost runs."""
    kept, dropped = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(int))
    for r in rows:
        try:
            v = float(r["overall"])
        except (KeyError, TypeError, ValueError):
            continue
        if (r.get("note") or "") == score_all.UNSCORABLE:
            dropped[r["task"]][r["arm"]] += 1
        else:
            kept[r["task"]][r["arm"]].append(v)
    arms, out = [], []
    for task in sorted(t for t in dropped if any(dropped[t].values())):
        for arm in sorted(set(kept[task]) | set(dropped[task])):
            x = kept[task][arm]
            arms.append({"task": task, "arm": arm, "n": len(x), "n_dropped": dropped[task][arm],
                         "mean": mean(x) if x else None, "sd": st.stdev(x) if len(x) > 1 else 0.0})
        for xa, ya in pairs:
            if not (dropped[task][xa] or dropped[task][ya]) or not kept[task][xa] or not kept[task][ya]:
                continue
            rng = random.Random(f"{seed}-{task}-{xa}-{ya}-posthoc")
            out.append({"task": task, "comparison": f"{xa} - {ya}", **compare(kept[task][xa], kept[task][ya], b, rng)})
    return arms, out


def md_pair(r, *lead):
    """One markdown comparison row: leading cells, then n, difference, CI, p and the equivalence verdict."""
    return "| " + " | ".join([r["comparison"], *lead, f"{r['n_x']} vs {r['n_y']}", f"{r['diff']:+.2f}",
                              f"{r['ci_lo']:+.2f} to {r['ci_hi']:+.2f}", f"{pfmt(r['p_perm'])} ({r['p_method']})",
                              "yes" if r["equivalent_1pp"] else "no"]) + " |"


def write_csv(name, rows, empty_cols):
    with open(os.path.join(RES, name), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else empty_cols); w.writeheader(); w.writerows(rows)


def pfmt(p):
    return "<0.0001" if p < 1e-4 else f"{p:.4f}"


def fmt(x, nd=2):
    return "" if x is None else f"{x:.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--b", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=20261116)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(os.path.join(RES, "scores.csv"))))
    ledger = {r["runid"]: r for r in csv.DictReader(open(os.path.join(RES, "runs.csv")))}
    acc = defaultdict(lambda: defaultdict(list))
    by_regime = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    vsets = defaultdict(lambda: defaultdict(set))
    have_raw = defaultdict(lambda: defaultdict(bool))
    for r in rows:
        try:
            v = float(r["overall"])
        except (KeyError, TypeError, ValueError):
            continue
        acc[r["task"]][r["arm"]].append(v)
        by_regime[r["task"]][r["arm"]][regime(ledger.get(r["runid"], {}))].append(v)
        run_dir = os.path.join(RES, "raw", r["arm"], r["task"], r["runid"])
        if os.path.isdir(run_dir) and r.get("scored_file"):
            h = value_set_hash(run_dir, r["scored_file"])
            if h:
                vsets[r["task"]][r["arm"]].add(h)
                have_raw[r["task"]][r["arm"]] = True

    out_arm, out_pair = [], []
    for task in sorted(acc):
        for arm in sorted(acc[task]):
            x = acc[task][arm]
            out_arm.append({"task": task, "arm": arm, "n": len(x), "mean": mean(x),
                            "sd": st.stdev(x) if len(x) > 1 else 0.0, "min": min(x), "max": max(x),
                            "distinct_value_sets": len(vsets[task][arm]) if have_raw[task][arm] else "n/a"})
        for xa, ya in PAIRS:
            if xa not in acc[task] or ya not in acc[task]:
                continue
            rng = random.Random(f"{a.seed}-{task}-{xa}-{ya}")
            out_pair.append({"task": task, "comparison": f"{xa} - {ya}",
                             **compare(acc[task][xa], acc[task][ya], a.b, rng)})
    sens_arm, sens_pair = sensitivity(by_regime, PAIRS, a.b, a.seed)
    ph_arm, ph_pair = posthoc_unscorable(rows, PAIRS, a.b, a.seed)

    write_csv("stats.csv", out_pair, ["task"])
    write_csv("stats_arms.csv", out_arm, ["task", "arm"])
    write_csv("stats_sensitivity.csv", sens_pair, ["task", "comparison", "split_arm", "regime"])
    write_csv("stats_sensitivity_arms.csv", sens_arm, ["task", "arm", "regime", "n", "mean", "sd"])
    write_csv("stats_posthoc.csv", ph_pair, ["task", "comparison"])
    write_csv("stats_posthoc_arms.csv", ph_arm, ["task", "arm", "n", "n_dropped", "mean", "sd"])

    md = ["# Pre-specified comparisons", "",
          f"Overall accuracy (paper metric, percentage points). Difference = mean(X) - mean(Y); 95% percentile "
          f"bootstrap CI over runs (B = {a.b:,}, seed {a.seed}); two-sided permutation p. Equivalent = whole CI inside "
          f"+/-{MARGIN} pp. With n = 3 in an arm the bootstrap has only 10 distinct resamples for it, so its CI is coarse. Generated by `scoring/stats.py`; do not edit by hand.", ""]
    for task in sorted(acc):
        md += [f"## {task}", "", "| Arm | n | Mean | SD | Min | Max | Distinct value sets |", "|---|---|---|---|---|---|---|"]
        md += [f"| {r['arm']} | {r['n']} | {fmt(r['mean'])} | {fmt(r['sd'])} | {fmt(r['min'])} | {fmt(r['max'])} | "
               f"{r['distinct_value_sets']} |" for r in out_arm if r["task"] == task]
        md += ["", "| Comparison | n | Difference | 95% CI | p (perm.) | Equivalent (±1 pp) |", "|---|---|---|---|---|---|"]
        md += [md_pair(r) for r in out_pair if r["task"] == task]
        md.append("")
        if any(r["task"] == task for r in sens_arm):
            md += [f"### {task}: sensitivity by isolation regime", "",
                   "Arms whose runs used more than one isolation regime, split by regime (user = user instructions "
                   "loaded, as in T1 runs 1-3; isolated = none). Pre-specified before the runs it splits.", "",
                   "| Arm | Regime | n | Mean | SD |", "|---|---|---|---|---|"]
            md += [f"| {r['arm']} | {r['regime']} | {r['n']} | {fmt(r['mean'])} | {fmt(r['sd'])} |"
                   for r in sens_arm if r["task"] == task]
            md += ["", "| Comparison | Split arm: regime | n | Difference | 95% CI | p (perm.) | Equivalent (±1 pp) |",
                   "|---|---|---|---|---|---|---|"]
            md += [md_pair(r, f"{r['split_arm']}: {r['regime']}") for r in sens_pair if r["task"] == task]
            md.append("")
        if any(r["task"] == task for r in ph_arm):
            md += [f"### {task}: post-hoc, without runs that had no scorable file", "",
                   "**Post-hoc** (decided after seeing the scores; logs/deviations.md §17). Completed runs whose individual "
                   "file could not be matched to any subject score 0 in the primary analysis above; here they are left out.",
                   "", "| Arm | n | Dropped | Mean | SD |", "|---|---|---|---|---|"]
            md += [f"| {r['arm']} | {r['n']} | {r['n_dropped']} | {fmt(r['mean'])} | {fmt(r['sd'])} |"
                   for r in ph_arm if r["task"] == task]
            md += ["", "| Comparison | n | Difference | 95% CI | p (perm.) | Equivalent (±1 pp) |", "|---|---|---|---|---|---|"]
            md += [md_pair(r) for r in ph_pair if r["task"] == task]
            md.append("")
    open(os.path.join(RES, "stats.md"), "w").write("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
