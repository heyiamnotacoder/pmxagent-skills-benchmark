#!/usr/bin/env python3
"""Protocol check for T2 (issue #7): does score_case_run read the agents' T2 files correctly?

Agents name T2 files and columns freely, so the scorer finds the simulated-data CSV and its columns by pattern
(`score_all.read_sim`). This script checks that by hand on a sample fixed in advance, not chosen by score:
  * the first two valid T2 reps of every arm (lowest rep numbers), and
  * every valid T2 run the scorer could not parse before this check (the 3 A2 runs counted in deviations §24).

For each sampled run the simulated-data file and its subject / time / concentration / dose columns were picked by
reading the file (HAND below). Independent code (pandas, its own AUC rule; nothing imported from score_all for the
arithmetic) then recomputes the per-dose mean Cmax and mean AUClast and the consistency percentage, and compares with
(1) what the scorer reports for the same run and (2) the results.json fields copied into results/scores.csv.

Writes logs/t2_parser_check.txt (the evidence) and results/t2_parser_check.csv (one row per run, for paper/tables.py).
Usage: check_t2_parser.py [--out logs/t2_parser_check.txt] [--csv results/t2_parser_check.csv]
"""
import argparse, csv, glob, json, math, os, sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "harness"))
import ledger
import score_all

RAW = os.path.join(ROOT, "results", "raw")

# Picked by reading each file's header and first rows: (simulated-data CSV, subject, time, concentration, dose).
HAND = {
    "A0_T2_case_r11_20261116-215941": ("output/simulated_pk.csv", "subject_id", "time_h", "conc", "dose_mg"),
    "A0_T2_case_r12_20261116-221549": ("output/pk_simulated.csv", "subject_id", "time_h", "conc", "dose_mg"),
    "A1_T2_case_r14_20261121-123011": ("output/pk_simulated_data.csv", "USUBJID", "TIME", "CONC", "DOSE"),
    "A1_T2_case_r15_20261121-123306": ("output/pk_simulation.csv", "USUBJID", "TIME", "CONC", "DOSE"),
    "A2_T2_case_r11_20261121-220918": ("output/pk_simulated.csv", "SUBJID", "time", "CONC", "DOSE_MG"),
    "A2_T2_case_r12_20261121-221419": ("output/simulated_pk.csv", "SUBJID", "TIME", "CONC", "DOSE"),
    "A2_T2_case_r21_20261121-224053": ("output/simulated_pk.csv", "SUBJID", "TIME", "CONC", "DOSE"),
    "A3_T2_case_r11_20261122-132223": ("output/pk_simulation.csv", "USUBJID", "TIME", "CONC", "DOSE"),
    "A3_T2_case_r12_20261122-132323": ("output/pk_simulation.csv", "USUBJID", "TIME", "CONC", "DOSE"),
    "A4_T2_case_r11_20261122-213144": ("output/pksim_results/pk_simulation.csv", "USUBJID", "TIME", "CONC", "DOSE"),
    # two concentration columns: both are checked (ALT_CONC); the scorer's pattern order picks conc_ng_ml
    "A4_T2_case_r12_20261122-213411": ("output/simulated_pk_data.csv", "global_id", "time_h", "conc_ng_ml", "dose_mg"),
}
ALT_CONC = {"A4_T2_case_r12_20261122-213411": ["conc_actual"]}
UNPARSEABLE_BEFORE = ["A2_T2_case_r11_20261121-220918", "A2_T2_case_r12_20261121-221419",
                      "A2_T2_case_r21_20261121-224053"]   # "sim file not parseable" in results/scores.csv, §24


def sample(rows):
    """First two valid T2 reps per arm, by rep number, plus the runs the scorer could not parse before."""
    ex = ledger.exclusions()
    valid = [r for r in rows if r["task"] == "T2_case" and ledger.valid(r, ex) and int(r["rep"]) > 0]
    out = []
    for arm in sorted({r["arm"] for r in valid}):
        out += [r["runid"] for r in sorted((r for r in valid if r["arm"] == arm), key=lambda r: int(r["rep"]))[:2]]
    return out + [x for x in UNPARSEABLE_BEFORE if x not in out]


def auc_lulog(t, c):
    """AUClast, linear up / log down, to the last positive concentration (written separately from score_all)."""
    o = np.argsort(t, kind="stable"); t, c = np.asarray(t, float)[o], np.asarray(c, float)[o]
    pos = np.nonzero(c > 0)[0]
    if not len(pos):
        return 0.0
    t, c = t[:pos[-1] + 1], c[:pos[-1] + 1]
    dt, c0, c1 = np.diff(t), c[:-1], c[1:]
    down = (c1 < c0) & (c1 > 0)
    with np.errstate(divide="ignore", invalid="ignore"):
        logpart = (c0 - c1) * dt / np.log(c0 / c1)
    return float(np.where(down, logpart, (c0 + c1) * dt / 2).sum())


def hand_check(run_dir, path, idc, tc, cc, dc, groups):
    d = pd.read_csv(os.path.join(run_dir, path))
    d = d[pd.to_numeric(d[cc], errors="coerce").notna() & pd.to_numeric(d[tc], errors="coerce").notna()]
    d = d.assign(_dose=d[dc].astype(str).str.replace(r"[^0-9.]", "", regex=True).astype(float))
    per = d.groupby(["_dose", idc]).apply(
        lambda s: pd.Series({"cmax": s[cc].astype(float).max(), "auc": auc_lulog(s[tc], s[cc])}), include_groups=False)
    ok, n, detail = 0, 0, []
    for dose, g in per.groupby(level=0):
        rep = groups.get(float(dose))
        if rep is None:
            continue
        for k, key in (("auc", "mean_AUClast"), ("cmax", "mean_Cmax")):
            mine, theirs = g[k].mean(), float(rep[key])
            re_ = abs(theirs - mine) / abs(mine) if mine else math.inf
            ok += re_ < 0.01; n += 1
            detail.append(f"{k}@{dose:g}: {re_ * 100:.2f}%")
    n_subj = per.shape[0]
    return n_subj, round(100 * ok / n, 1) if n else None, ", ".join(detail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "logs", "t2_parser_check.txt"))
    ap.add_argument("--csv", default=os.path.join(ROOT, "results", "t2_parser_check.csv"))
    a = ap.parse_args()
    runs = list(csv.DictReader(open(os.path.join(ROOT, "results", "runs.csv"))))
    scores = {r["runid"]: r for r in csv.DictReader(open(os.path.join(ROOT, "results", "scores.csv")))}
    picked = sample(runs)
    missing = [x for x in picked if x not in HAND]
    if missing:
        sys.exit(f"sample has runs without a hand column map: {missing}")
    L = ["T2 parser check (issue #7). Sample rule: first two valid reps per arm by rep number + every run the scorer",
         "could not parse before this check. Columns picked by hand; consistency recomputed with independent code.",
         "consistency = % of the 6 per-dose checks (mean AUClast lin-up/log-down, mean Cmax) within 1% of results.json.",
         ""]
    n_agree, table = 0, []
    for runid in picked:
        arm = runid.split("_")[0]
        run_dir = os.path.join(RAW, arm, "T2_case", runid)
        path, idc, tc, cc, dc = HAND[runid]
        j = json.load(open(glob.glob(os.path.join(run_dir, "output", "**", "results.json"), recursive=True)[0]))
        groups = {float(str(g["dose_mg"]).strip()): g for g in j["group_summary"]}
        n_subj, cons, detail = hand_check(run_dir, path, idc, tc, cc, dc, groups)
        s = score_all.score_case_run(run_dir)
        cols = list(pd.read_csv(os.path.join(run_dir, path), nrows=0).columns)
        picks = score_all.sim_columns(cols).values()
        row = scores.get(runid, {})
        fields_ok = all(str(row.get(k, "")) == str("" if j.get(src) is None else j.get(src))
                        for k, src in (("ec50", "ec50"), ("ec50_units", "ec50_units"), ("seed", "seed"),
                                       ("n_timepoints", "n_timepoints_per_subject")))
        agree = (s.get("sim_file") == path and s.get("n_subjects_sim") == n_subj
                 and s.get("summary_consistent_pct") == cons)
        n_agree += agree
        table.append({"runid": runid, "arm": arm, "unparseable_before": runid in UNPARSEABLE_BEFORE,
                      "hand_consistent_pct": cons, "scorer_consistent_pct": s.get("summary_consistent_pct"),
                      "fields_match": fields_ok, "agree": agree})
        L += [f"{runid}",
              f"  file      hand {path} | scorer {s.get('sim_file')}",
              f"  columns   hand {idc}/{tc}/{cc}/{dc} | scorer {'/'.join(str(p) for p in picks)}",
              f"  subjects  hand {n_subj} | scorer {s.get('n_subjects_sim')}",
              f"  consistent hand {cons} | scorer now {s.get('summary_consistent_pct')} | scores.csv "
              f"{row.get('summary_consistent_pct') or '(' + (row.get('note') or 'blank') + ')'}",
              f"  per dose (|RE| hand vs results.json): {detail}",
              f"  results.json fields in scores.csv (ec50, units, seed, n_timepoints) match: {fields_ok}",
              f"  scorer agrees with hand check: {agree}"]
        for alt in ALT_CONC.get(runid, []):
            n2, c2, d2 = hand_check(run_dir, path, idc, tc, alt, dc, groups)
            L.append(f"  alt conc column {alt}: consistent {c2} ({d2})")
        L.append("")
    L.append(f"scorer agrees with the hand check on {n_agree} of {len(picked)} sampled runs")
    open(a.out, "w").write("\n".join(L) + "\n")
    with open(a.csv, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(table[0])); w.writeheader(); w.writerows(table)
    print("\n".join(L))


if __name__ == "__main__":
    main()
