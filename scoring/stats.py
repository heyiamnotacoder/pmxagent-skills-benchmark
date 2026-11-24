#!/usr/bin/env python3
"""Pre-specified arm comparisons (paper/SPEC.md, "Pre-specified analysis") -> results/stats.md + results/stats.csv.

For each task with a run-level accuracy (`overall` in results/scores.csv) and each pre-specified pair (X - Y):
  - difference in mean accuracy, 95% percentile bootstrap CI (resample runs within each arm; B = 10,000; fixed seed)
  - two-sided permutation p-value (exact when the number of splits is <= 200,000, else 100,000 random splits)
  - equivalence vs the +/-1.0 percentage-point margin: "equivalent" only if the whole 95% CI lies inside the margin
Per arm: n, mean, SD, min, max, and the number of distinct parameter-value sets (needs results/raw/; else "n/a");
for NCA tasks also the terminal-point match and how many lambda-z-dependent errors fall in subjects whose terminal
points differ from PKanalix (descriptive, post hoc; logs/deviations.md §26; needs results/raw/ and the reference).
Sensitivity (pre-specified 2026-11-17, before A1 T1 runs 4-10; logs/deviations.md §15): for an arm whose runs in a
task used more than one isolation regime (ledger `claude_config`: empty/"user" = user instructions loaded, as in T1;
"isolated" = none), per-regime arm stats and every pair involving that arm recomputed on each regime alone.
Post-hoc sensitivity (decided 2026-11-20 after seeing T1 scores; logs/deviations.md §17; labelled post-hoc): in each
task where a completed run had no scorable individual file (scored 0 under the primary rule), per-arm stats and every
pair involving an arm that lost runs, recomputed without those runs -> results/stats_posthoc.csv.
Post-hoc upper bound (decided 2026-11-24 after the peer review; logs/deviations.md §29): each run scored by matching
drug-only rows in input order is also scored in character order of subject number (1, 10, 2, ...) and the higher
score kept -> results/stats_charorder{,_arms}.csv. It uses the reference to pick the order, so never the primary rule.
Distinct value sets: hashed on the seven scored parameters only, empty cells left out (Methods 2.5; §29).
Descriptive, post hoc (logs/deviations.md §30): where each T1 arm's AUClast errors fall relative to subjects with a
BLQ record after Tmax -> results/stats_blq.csv.
Per-arm rows of the sensitivity analyses: results/stats_{sensitivity,posthoc,charorder}_arms.csv (read by paper/tables.py).
Valid runs only (scores.csv already holds only those). Stdlib only.  Usage: stats.py [--b 10000] [--seed 20261116]
"""
import argparse, csv, functools, glob, hashlib, itertools, math, os, random, statistics as st, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_all
import score_nca as sn
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
PAIRS = [("A2", "A1"), ("A3", "A1"), ("A3", "A2"), ("A4", "A3"), ("A0", "A3")]
SECONDARY_PAIRS = [("A1b", "A1"), ("A2", "A1b"), ("A3", "A1b"), ("A4", "A1b")]   # pre-specified secondary arm (§21)
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


def value_set_hash(d):
    """Hash of a scored individual table as Methods 2.5 defines it: (subject, parameter, value at 6 significant
    digits) for the seven scored parameters, empty cells left out, sorted (peer review S3; logs/deviations.md §29)."""
    items = sorted((s, k, f"{v:.6g}") for (s, k), v in d.items() if k in sn.PARAMS and not math.isnan(v))
    return hashlib.sha256(repr(items).encode()).hexdigest()


def terminal_points(breakdowns):
    """Pool score_nca.terminal_point_breakdown over an arm's runs (None = run reported no terminal-point count, left
    out). Descriptive, decided after the results were seen (logs/deviations.md §26): `npts_runs` runs reporting,
    `npts_match_pct` of their subjects with PKanalix's number of points, `lz_errors` lambda-z-dependent values outside
    1%, and how many of those are in subjects whose count differs / is missing / matches
    (`lz_errors_npts_differ` / `_none` / `_match`)."""
    bs = [b for b in breakdowns if b is not None]
    tot = {k: sum(b[k] for b in bs) for k in sn.BREAKDOWN_KEYS}
    split = {f"lz_errors_npts_{g}": tot[f"lz_{g}_err"] for g in ("differ", "none", "match")}
    if not tot["subjects"]:
        return {"npts_runs": len(bs), **dict.fromkeys(("npts_match_pct", "lz_errors", *split), "n/a")}
    return {"npts_runs": len(bs), "npts_match_pct": round(100 * tot["match"] / tot["subjects"], 2),
            "lz_errors": sum(split.values()), **split}


@functools.lru_cache(maxsize=None)
def nca_ref(task):
    """PKanalix reference of an NCA task, or None where it is not built (git-ignored; `tasks/build_tasks.py`)."""
    p = os.path.join(ROOT, "tasks", task, "reference", "pkanalix_individual.csv")
    return sn.load(p) if os.path.exists(p) else None


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


def subset_stats(acc, affected, pairs, b, seed, tag, count_key, all_arms):
    """Arm stats and pair comparisons for the tasks where `affected[task][arm]` (a count) is non-zero. acc[task][arm]
    = accuracies to use. Arms: every arm of such a task (`all_arms`) or only the affected ones; pairs: those involving
    an affected arm. Shared by the post hoc analyses below; `tag` keeps each one's bootstrap stream apart."""
    arms, out = [], []
    for task in sorted(t for t in affected if any(affected[t].values())):
        names = set(acc[task]) | set(affected[task]) if all_arms else {a for a, k in affected[task].items() if k}
        for arm in sorted(names):
            x = acc[task][arm]
            arms.append({"task": task, "arm": arm, "n": len(x), count_key: affected[task][arm],
                         "mean": mean(x) if x else None, "sd": st.stdev(x) if len(x) > 1 else 0.0})
        for xa, ya in pairs:
            if (affected[task][xa] or affected[task][ya]) and acc[task][xa] and acc[task][ya]:
                rng = random.Random(f"{seed}-{task}-{xa}-{ya}-{tag}")
                out.append({"task": task, "comparison": f"{xa} - {ya}", **compare(acc[task][xa], acc[task][ya], b, rng)})
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
    return subset_stats(kept, dropped, pairs, b, seed, "posthoc", "n_dropped", all_arms=True)


def with_replacements(rows, repl, pairs, b, seed):
    """Post-hoc upper bound (logs/deviations.md §29): rows are scores.csv dicts, `repl` {runid: overall} the scores of
    runs re-scored another way. Returns (arm stats, pair comparisons) for tasks and arms with a replaced run, and the
    pairs involving such an arm."""
    acc, hit = defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(int))
    for r in rows:
        try:
            v = float(repl.get(r["runid"], r["overall"]))
        except (KeyError, TypeError, ValueError):
            continue
        acc[r["task"]][r["arm"]].append(v)
        hit[r["task"]][r["arm"]] += r["runid"] in repl
    return subset_stats(acc, hit, pairs, b, seed, "charorder", "n_replaced", all_arms=False)


def favourable_order_scores(rows):
    """{runid: overall_charorder} for runs scored by row order whose drug-only rows score higher matched in character
    order of subject number (scores.csv `overall_charorder`, written by score_all.py). Picking the higher of the two
    orders uses the reference, so this is an upper bound, labelled post hoc, never the primary rule (§29)."""
    out = {}
    for r in rows:
        try:
            alt, now = float(r.get("overall_charorder") or "nan"), float(r["overall"])
        except (KeyError, TypeError, ValueError):
            continue
        if alt > now:
            out[r["runid"]] = alt
    return out


def post_tmax_blq_subjects(input_rows):
    """Subjects (drug_subject) with a BLQ observation after their Tmax in a task input (DRUG, USUBJID, EVID, ATPTN,
    AVAL, BLQ). Post hoc, descriptive (logs/deviations.md §30)."""
    obs = defaultdict(list)
    for r in input_rows:
        if r["EVID"] == "0":
            obs[f"{r['DRUG']}_{r['USUBJID']}"].append((float(r["ATPTN"]), r["AVAL"], r["BLQ"]))
    out = set()
    for s, pts in obs.items():
        vals = [(t, float(a)) for t, a, b in pts if b != "1" and a not in (".", "")]
        if vals:
            tmax = max(vals, key=lambda x: x[1])[0]
            if any(b == "1" and t > tmax for t, _, b in pts):
                out.add(s)
    return out


def auclast_error_split(run, ref, blq):
    """(AUClast values outside 1% of the reference, of which in `blq` subjects) for one run's table."""
    err = [s for s, p in ref if p == "AUClast" and sn.rel_err(run.get((s, p)), ref[(s, p)]) >= 0.01]
    return len(err), sum(s in blq for s in err)


def blq_split(rows, task="T1_nca"):
    """Per arm: runs, runs with an AUClast error, runs whose AUClast errors all fall in post-Tmax-BLQ subjects, total
    errors and errors in those subjects; plus the number of such subjects. Needs results/raw/ and the task input."""
    ref, inp = nca_ref(task), os.path.join(ROOT, "tasks", task, "inputs", "nca_benchmark.csv")
    if ref is None or not os.path.exists(inp):
        return []
    blq = post_tmax_blq_subjects(csv.DictReader(open(inp)))
    by = defaultdict(lambda: {"runs": 0, "runs_err": 0, "runs_all_blq": 0, "err": 0, "err_blq": 0})
    for r in rows:
        if r["task"] != task:
            continue
        d = score_all.load_scored(os.path.join(RES, "raw", r["arm"], task, r["runid"]), r.get("scored_file"), ref)
        if d is None:
            continue
        n, nb = auclast_error_split(d, ref, blq)
        b = by[r["arm"]]
        b["runs"] += 1; b["runs_err"] += n > 0; b["runs_all_blq"] += n > 0 and n == nb
        b["err"] += n; b["err_blq"] += nb
    return [{"task": task, "arm": a, "blq_subjects": len(blq), **by[a]} for a in sorted(by)]


def md_pair(r, *lead):
    """One markdown comparison row: leading cells, then n, difference, CI, p and the equivalence verdict."""
    return "| " + " | ".join([r["comparison"], *lead, f"{r['n_x']} vs {r['n_y']}", f"{r['diff']:+.2f}",
                              f"{r['ci_lo']:+.2f} to {r['ci_hi']:+.2f}", f"{pfmt(r['p_perm'])} ({r['p_method']})",
                              "yes" if r["equivalent_1pp"] else "no"]) + " |"


def write_csv(name, rows, empty_cols):
    with open(os.path.join(RES, name), "w", newline="") as f:
        cols = list(dict.fromkeys(k for r in rows for k in r)) if rows else empty_cols   # keys in first-seen order
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)


def pfmt(p):
    return "<0.0001" if p < 1e-4 else f"{p:.4f}"


def fmt(x, nd=2):
    return "" if x is None else f"{x:.{nd}f}"


def compare_pairs(by_arm, task, pairs, b, seed, suffix=""):
    """Compare each (xa, ya) in `pairs` where both arms have runs in `by_arm`."""
    out = []
    for xa, ya in pairs:
        if xa not in by_arm or ya not in by_arm:
            continue
        rng = random.Random(f"{seed}-{task}-{xa}-{ya}{suffix}")
        out.append({"task": task, "comparison": f"{xa} - {ya}", **compare(by_arm[xa], by_arm[ya], b, rng)})
    return out


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
    tpts = defaultdict(lambda: defaultdict(list))   # task -> arm -> terminal_point_breakdown per run with raw files
    for r in rows:
        try:
            v = float(r["overall"])
        except (KeyError, TypeError, ValueError):
            continue
        acc[r["task"]][r["arm"]].append(v)
        by_regime[r["task"]][r["arm"]][regime(ledger.get(r["runid"], {}))].append(v)
        ref = nca_ref(r["task"]) if r["task"] in score_all.NCA_TASKS else None
        d = (score_all.load_scored(os.path.join(RES, "raw", r["arm"], r["task"], r["runid"]), r.get("scored_file"), ref)
             if ref is not None else None)
        if d is not None:
            vsets[r["task"]][r["arm"]].add(value_set_hash(d))
            have_raw[r["task"]][r["arm"]] = True
            tpts[r["task"]][r["arm"]].append(sn.terminal_point_breakdown(d, ref))

    out_arm, out_pair, out_sec = [], [], []
    for task in sorted(acc):
        for arm in sorted(acc[task]):
            x = acc[task][arm]
            out_arm.append({"task": task, "arm": arm, "n": len(x), "mean": mean(x),
                            "sd": st.stdev(x) if len(x) > 1 else 0.0, "min": min(x), "max": max(x),
                            "distinct_value_sets": len(vsets[task][arm]) if have_raw[task][arm] else "n/a",
                            **(terminal_points(tpts[task][arm]) if task in score_all.NCA_TASKS else {})})
        out_pair += compare_pairs(acc[task], task, PAIRS, a.b, a.seed)
        out_sec += compare_pairs(acc[task], task, SECONDARY_PAIRS, a.b, a.seed, suffix="-secondary")
    sens_arm, sens_pair = sensitivity(by_regime, PAIRS, a.b, a.seed)
    ph_arm, ph_pair = posthoc_unscorable(rows, PAIRS, a.b, a.seed)
    co_arm, co_pair = with_replacements(rows, favourable_order_scores(rows), PAIRS + SECONDARY_PAIRS, a.b, a.seed)

    write_csv("stats.csv", out_pair, ["task"])
    write_csv("stats_secondary.csv", out_sec, ["task", "comparison"])
    write_csv("stats_arms.csv", out_arm, ["task", "arm"])
    write_csv("stats_sensitivity.csv", sens_pair, ["task", "comparison", "split_arm", "regime"])
    write_csv("stats_sensitivity_arms.csv", sens_arm, ["task", "arm", "regime", "n", "mean", "sd"])
    write_csv("stats_posthoc.csv", ph_pair, ["task", "comparison"])
    write_csv("stats_posthoc_arms.csv", ph_arm, ["task", "arm", "n", "n_dropped", "mean", "sd"])
    write_csv("stats_blq.csv", blq_split(rows), ["task", "arm"])
    write_csv("stats_charorder.csv", co_pair, ["task", "comparison"])
    write_csv("stats_charorder_arms.csv", co_arm, ["task", "arm", "n", "n_replaced", "mean", "sd"])

    md = ["# Pre-specified comparisons", "",
          f"Overall accuracy (paper metric, percentage points). Difference = mean(X) - mean(Y); 95% percentile "
          f"bootstrap CI over runs (B = {a.b:,}, seed {a.seed}); two-sided permutation p. Equivalent = whole CI inside "
          f"+/-{MARGIN} pp. With n = 3 in an arm the bootstrap has only 10 distinct resamples for it, so its CI is coarse. Generated by `scoring/stats.py`; do not edit by hand.", ""]
    for task in sorted(acc):
        nca = task in score_all.NCA_TASKS
        md += [f"## {task}", "", "| Arm | n | Mean | SD | Min | Max | Distinct value sets |" +
               (" Runs with terminal points | Terminal points match (%) | λz errors (in differing subjects) |" if nca else ""),
               "|---|---|---|---|---|---|---|" + ("---|---|---|" if nca else "")]
        md += [f"| {r['arm']} | {r['n']} | {fmt(r['mean'])} | {fmt(r['sd'])} | {fmt(r['min'])} | {fmt(r['max'])} | "
               f"{r['distinct_value_sets']} |" +
               (f" {r['npts_runs']} | {r['npts_match_pct']} | {r['lz_errors']} ({r['lz_errors_npts_differ']}) |" if nca else "")
               for r in out_arm if r["task"] == task]
        md += ["", "| Comparison | n | Difference | 95% CI | p (perm.) | Equivalent (±1 pp) |", "|---|---|---|---|---|---|"]
        md += [md_pair(r) for r in out_pair if r["task"] == task]
        md.append("")
        if any(r["task"] == task for r in out_sec):
            md += [f"### {task}: secondary arm A1b (PMxAgent MCP + shipped CLAUDE.md)", "",
                   "Pre-specified before any A1b run (paper/SPEC.md; logs/deviations.md §21). Reported alongside "
                   "primary A1, never instead of it.", "",
                   "| Comparison | n | Difference | 95% CI | p (perm.) | Equivalent (±1 pp) |", "|---|---|---|---|---|---|"]
            md += [md_pair(r) for r in out_sec if r["task"] == task]
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
        if any(r["task"] == task for r in co_arm):
            md += [f"### {task}: post-hoc upper bound, drug-only files in character order", "",
                   "**Post-hoc** (decided after the peer review; logs/deviations.md §29). Runs scored by matching drug-only "
                   "rows in input order are also matched in character order of subject number (1, 10, 2, ...), and the "
                   "higher score is kept. Choosing the order uses the reference, so this is an upper bound, never the "
                   "primary rule.", "", "| Arm | n | Replaced | Mean | SD |", "|---|---|---|---|---|"]
            md += [f"| {r['arm']} | {r['n']} | {r['n_replaced']} | {fmt(r['mean'])} | {fmt(r['sd'])} |"
                   for r in co_arm if r["task"] == task]
            md += ["", "| Comparison | n | Difference | 95% CI | p (perm.) | Equivalent (±1 pp) |", "|---|---|---|---|---|---|"]
            md += [md_pair(r) for r in co_pair if r["task"] == task]
            md.append("")
    open(os.path.join(RES, "stats.md"), "w").write("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
