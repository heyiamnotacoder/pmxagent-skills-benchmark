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
import argparse, csv, json, math, os, re, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(HERE, "..", "psp470325-sup-0001-appendixs1", "benchmark")
REF = os.path.join(BENCH, "Single Run Analysis", "nca_results_PKanalix_individual.csv")

# Parameter names per scored quantity, matched through `canonical`: case, `. _ / -` and spaces are ignored, so one
# entry covers every punctuation variant (`cl_obs` = `cl.obs` = `CLobs`). Sources: the paper's and PKanalix's names,
# CDISC PPTESTCD codes, PKNCA's codes (`PKNCA::get.interval.cols()`, observed values only: no `.pred`, `.dn`,
# `r.squared`, `clast.*`) and spellings logged in logs/deviations.md §5. Matched by rule, not by adding names seen
# in runs (§29).
NAMES = {
    "Cmax": ["cmax"],
    "Tmax": ["tmax"],
    "AUClast": ["auclast", "auclst"],
    "AUCINF_obs": ["aucinf_obs", "aucinf", "aucifobs", "aucifo"],
    "HL": ["half_life", "hl_lambda_z", "thalf", "lamzhl"],
    "CL": ["cl_obs", "clf_obs", "cl", "clf", "clo", "clfo"],
    "Vz": ["vz_obs", "vzf_obs", "vz", "vzf", "vzo", "vzfo"],
    "R2ADJ": ["adj_r_squared", "rsq_adjusted", "r2adj", "lamzr2a", "adj_r2"],
    "NPTS": ["lambda_z_n_points", "no_points_lambda_z", "lamznpt", "n_lambda_z", "n_terminal"],
}
ALL_SUBJ = ["Cmax", "Tmax", "AUClast"]
LZ_DEP = ["AUCINF_obs", "HL", "CL", "Vz"]
PARAMS = ALL_SUBJ + LZ_DEP

PUBLISHED = {  # file stem -> published overall accuracy (%)
    "PMxAgent": 98.3, "Claude_Opus_48": 98.2, "GPT55_pro": 95.6,
    "Claude_Sonnet_46": 94.5, "GPT55_thinking": 91.6,
}


def _norm(name):
    return re.sub(r"[._/\-\s]", "", str(name or "").strip().lower())


_CANON = {_norm(n): p for p, names in NAMES.items() for n in names}


def canonical(name):
    """The scored parameter (or R2ADJ / NPTS) a column or PPTESTCD name stands for, or None."""
    return _CANON.get(_norm(name))


SUBJECT_COLS = ("usubjid", "subjid", "subject", "id")   # a subject column next to DRUG, first match wins


def read_rows(path):
    """Long-format rows (DRUG, PPTESTCD, PPSTRESN[, subject column]) as (id, parameter, value) in file order; id is
    `drug_subject` when a subject column (SUBJECT_COLS) is filled, else DRUG as written (a subject key, or a drug name
    only, which `to_table` may match by row order)."""
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        low = {c.strip().lower(): c for c in rd.fieldnames or []}
        cols = {k: low[k] for k in ("drug", "pptestcd", "ppstresn") if k in low}
        sc = next((low[c] for c in SUBJECT_COLS if c in low), None)
        for row in rd:
            p = canonical(row[cols["pptestcd"]])
            if p is None:
                continue
            try:
                v = float(row[cols["ppstresn"]])
            except (TypeError, ValueError):
                v = math.nan
            subj = row[cols["drug"]].strip()
            sid = (row.get(sc) or "").strip() if sc else ""
            if sid and not subj.endswith("_" + sid):   # DRUG + subject -> drug_subject
                subj = f"{subj}_{sid}"
            rows.append((subj, p, v))
    return rows


def subject_order(ref, character=False):
    """{drug: [subject keys]} in the reference file's order, which is the task input's order (checked for every NCA
    task when §29 was decided). `character=True`: subject numbers sorted as text (1, 10, 2, ...), for the post hoc
    sensitivity only, never the primary rule."""
    order = defaultdict(list)
    for s, _ in ref:
        drug = s.rsplit("_", 1)[0]
        if s not in order[drug]:
            order[drug].append(s)
    if character:
        return {d: sorted(ss, key=lambda s: s.rsplit("_", 1)[1]) for d, ss in order.items()}
    return dict(order)


def to_table(rows, order=None):
    """{(subject, parameter): value} from (id, parameter, value) rows. With `order` (subject_order of the reference),
    rows whose id is a drug name rather than a subject are matched by row order, the same rule for every arm
    (logs/deviations.md §29): within a drug and parameter the k-th row is the drug's k-th subject, but only when the
    number of rows equals the drug's number of subjects; otherwise that drug and parameter stay missing.
    Returns (table, n_matched_by_row_order)."""
    subjects = {s for ss in (order or {}).values() for s in ss}
    out, groups = {}, defaultdict(list)
    for s, p, v in rows:
        if order and s not in subjects and s in order:
            groups[(s, p)].append(v)
        else:
            out[(s, p)] = v
    matched = 0
    for (drug, p), vs in groups.items():
        if len(vs) == len(order[drug]):
            for s, v in zip(order[drug], vs):
                out.setdefault((s, p), v)
                matched += 1
    return out, matched


def load(path, order=None):
    return to_table(read_rows(path), order)[0]


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
                ok_ref, ok_ag = _r2_ok(ref, s), _r2_ok(agent, s)
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
    # terminal-point match (reported separately, not in overall; a run without NPTS counts every subject as differing)
    npts_subj = _npts_subjects(ref)
    m = sum(agent.get((s, "NPTS")) == ref[(s, "NPTS")] for s in npts_subj)
    res["terminal_points_match_pct"] = 100 * m / len(npts_subj) if npts_subj else math.nan
    res["overall"] = sum(res[p]["correct_pct"] for p in PARAMS) / len(PARAMS)
    return res


def _r2_ok(table, s):
    """Adjusted R2 of subject `s` in `table` is >= 0.80 (the paper's filter for lambda-z-dependent parameters)."""
    r = table.get((s, "R2ADJ"), math.nan)
    return not math.isnan(r) and r >= 0.80


def _npts_subjects(ref):
    """Subjects with a reference terminal-point count and PKanalix adjusted R2 >= 0.80 (scored for lambda-z)."""
    return [s for s in sorted({s for s, _ in ref}) if (s, "NPTS") in ref and _r2_ok(ref, s)]


BREAKDOWN_KEYS = ("subjects", "match", "lz_match_n", "lz_match_err", "lz_differ_n", "lz_differ_err",
                  "lz_none_n", "lz_none_err")


def terminal_point_breakdown(agent, ref):
    """Terminal-point match and where the lambda-z-dependent errors fall, for one run (descriptive; not in `overall`).
    None if the run reported no terminal-point count for any subject. Otherwise, over subjects scored for lambda-z:
    `subjects` and `match` (same number of points as PKanalix). Each subject falls in one group: `match`, `differ`
    (a count other than PKanalix's) or `none` (no count for that subject); per group, the lambda-z-dependent values
    (AUCINF_obs, HL, CL, Vz) scored (`lz_<group>_n`) and outside 1% (`lz_<group>_err`). Keys: BREAKDOWN_KEYS."""
    if not any(p == "NPTS" for _, p in agent):
        return None
    b = dict.fromkeys(BREAKDOWN_KEYS, 0)
    for s in _npts_subjects(ref):
        n = agent.get((s, "NPTS"))
        group = "none" if n is None or math.isnan(n) else "match" if n == ref[(s, "NPTS")] else "differ"
        b["subjects"] += 1
        b["match"] += group == "match"
        for p in LZ_DEP:
            if (s, p) in ref:
                b[f"lz_{group}_n"] += 1
                b[f"lz_{group}_err"] += rel_err(agent.get((s, p)), ref[(s, p)]) >= 0.01
    return b


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
