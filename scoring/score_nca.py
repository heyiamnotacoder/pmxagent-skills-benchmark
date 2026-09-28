#!/usr/bin/env python3
"""Score NCA results against the PKanalix reference, reproducing the PMxAgent paper's metric.

Metric (Bloomingdale & Khot 2026, Methods 2.5 / Fig 6-7):
  - per subject, per parameter: |RE| vs PKanalix < 1% = correct, 1-5% = acceptable, >=5% = incorrect
  - Cmax, Tmax, AUClast: all subjects
  - HL, AUCINF_obs, CL, Vz (lambda-z dependent): only subjects with adjusted R2 >= 0.80
  - parameter accuracy = % correct; overall = mean of the 7 parameter accuracies
Stdlib only.

Usage:
  score_nca.py <individual.csv> [--ref REF] [--json]
  score_nca.py --calibrate          # re-score the paper's published CSVs, compare with published numbers
"""
import argparse, csv, json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(HERE, "..", "psp470325-sup-0001-appendixs1", "benchmark")
REF = os.path.join(BENCH, "Single Run Analysis", "nca_results_PKanalix_individual.csv")

ALIASES = {
    "cmax": "Cmax", "tmax": "Tmax", "auclast": "AUClast",
    "aucinf_obs": "AUCINF_obs", "aucinf": "AUCINF_obs",
    "hl_lambda_z": "HL", "half.life": "HL", "thalf": "HL",
    "cl_obs": "CL", "clf_obs": "CL", "cl": "CL", "clf": "CL",
    "vz_obs": "Vz", "vzf_obs": "Vz", "vz": "Vz", "vzf": "Vz",
    "rsq_adjusted": "R2ADJ", "adj.r.squared": "R2ADJ",
    "no_points_lambda_z": "NPTS", "lambda.z.n.points": "NPTS",
    # CDISC PPTESTCD codes (PMxAgent raw output, our skills' output)
    "auclst": "AUClast", "aucifobs": "AUCINF_obs", "lamzhl": "HL",
    "clobs": "CL", "clfobs": "CL", "vzobs": "Vz", "vzfobs": "Vz",
    "r2adj": "R2ADJ", "lamznpt": "NPTS",
    # other spellings seen in agent outputs (naming is not scored; values are)
    "aucifo": "AUCINF_obs", "clo": "CL", "clfo": "CL", "vzo": "Vz", "vzfo": "Vz",
    "cl_f_obs": "CL", "vz_f_obs": "Vz", "lamzr2a": "R2ADJ", "adj_r2": "R2ADJ", "adjr2": "R2ADJ",
    "n_lambda_z": "NPTS", "n_terminal": "NPTS",
    "cl/f_obs": "CL", "vz/f_obs": "Vz", "cl/f": "CL", "vz/f": "Vz", "adj_r_squared": "R2ADJ",
}
ALL_SUBJ = ["Cmax", "Tmax", "AUClast"]
LZ_DEP = ["AUCINF_obs", "HL", "CL", "Vz"]
PARAMS = ALL_SUBJ + LZ_DEP

PUBLISHED = {  # file stem -> published overall accuracy (%)
    "PMxAgent": 98.3, "Claude_Opus_48": 98.2, "GPT55_pro": 95.6,
    "Claude_Sonnet_46": 94.5, "GPT55_thinking": 91.6,
}


def load(path):
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            p = ALIASES.get(row["PPTESTCD"].strip().lower())
            if p is None:
                continue
            try:
                v = float(row["PPSTRESN"])
            except (TypeError, ValueError):
                v = math.nan
            subj = row["DRUG"].strip()
            if row.get("USUBJID"):  # long CDISC format: DRUG + USUBJID -> drug_subject
                subj = f"{subj}_{row['USUBJID'].strip()}"
            out[(subj, p)] = v
    return out


def rel_err(x, ref):
    if x is None or math.isnan(x) or math.isnan(ref):
        return math.inf
    if ref == 0:
        return 0.0 if x == 0 else math.inf
    return abs(x - ref) / abs(ref)


def score(agent, ref, r2_filter="ref", missing="incorrect"):
    subjects = sorted({s for s, _ in ref})
    res = {}
    for p in PARAMS:
        n = correct = acceptable = 0
        for s in subjects:
            if (s, p) not in ref:
                continue
            if p in LZ_DEP:
                r_ref = ref.get((s, "R2ADJ"), math.nan)
                r_ag = agent.get((s, "R2ADJ"), math.nan)
                ok_ref = not math.isnan(r_ref) and r_ref >= 0.80
                ok_ag = not math.isnan(r_ag) and r_ag >= 0.80
                keep = {"ref": ok_ref, "both": ok_ref and ok_ag, "agent": ok_ag}[r2_filter]
                if not keep:
                    continue
            x = agent.get((s, p))
            if x is None and missing == "exclude":
                continue
            n += 1
            e = rel_err(x, ref[(s, p)])
            correct += e < 0.01
            acceptable += 0.01 <= e < 0.05
        res[p] = {"n": n, "correct_pct": 100 * correct / n if n else math.nan,
                  "acceptable_pct": 100 * acceptable / n if n else math.nan}
    # terminal-point match (reported separately, not in overall)
    n = m = 0
    for s in subjects:
        r_ref = ref.get((s, "R2ADJ"), math.nan)
        if (s, "NPTS") in ref and not math.isnan(r_ref) and r_ref >= 0.80:
            n += 1
            m += agent.get((s, "NPTS")) == ref[(s, "NPTS")]
    res["terminal_points_match_pct"] = 100 * m / n if n else math.nan
    res["overall"] = sum(res[p]["correct_pct"] for p in PARAMS) / len(PARAMS)
    return res


def fmt(name, r):
    cols = " ".join(f"{p}={r[p]['correct_pct']:.1f}" for p in PARAMS)
    return f"{name:18s} overall={r['overall']:.2f}  {cols}  npts_match={r['terminal_points_match_pct']:.1f}"


def calibrate(ref_path, tol=0.1):
    """Gate: default rule (PKanalix R2adj >= 0.80 filter, missing value = incorrect) must
    reproduce the published overall accuracies. Other rule variants were tried and give up to 0.3 off."""
    ref = load(ref_path)
    single = os.path.join(BENCH, "Single Run Analysis")
    worst = 0.0
    for stem, pub in PUBLISHED.items():
        r = score(load(os.path.join(single, f"nca_results_{stem}_individual.csv")), ref)
        worst = max(worst, abs(round(r["overall"], 1) - pub))
        print(fmt(stem, r) + f"  published={pub}")
    ok = worst <= tol
    print(f"max |diff| = {worst:.2f} -> {'PASS' if ok else 'FAIL'} (tol {tol})")
    return ok

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--ref", default=REF)
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--r2-filter", default="ref", choices=["ref", "both", "agent"])
    ap.add_argument("--missing", default="incorrect", choices=["incorrect", "exclude"])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.calibrate:
        ok = calibrate(a.ref)
        sys.exit(0 if ok else 1)
    ref = load(a.ref)
    for f in a.files:
        r = score(load(f), ref, a.r2_filter, a.missing)
        print(json.dumps({"file": f, **r}, default=float) if a.json else fmt(os.path.basename(f), r))


if __name__ == "__main__":
    main()
