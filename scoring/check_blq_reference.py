#!/usr/bin/env python3
"""Protocol check before running T3b: which BLQ rule does the PKanalix reference follow?

The T3b prompt states: BLQ before Tmax = 0, BLQ after Tmax = missing. In the input data every BLQ record has AVAL = 0.
If PKanalix used the zeros as given, the T3b reference does not follow the prompt's rule, and scoring T3b against
it would penalise agents for obeying the prompt.

Method: for every subject with a BLQ record after Tmax (the only subjects where the rules differ), compute AUClast
(linear-up/log-down, independent code, no skill code) from the input under each rule and compare with PKanalix
AUClast (|RE| < 1% = match). Uses only the input data and the reference; never looks at agent output.

Usage: check_blq_reference.py [--data tasks/T3b_blq/inputs/nca_blq.csv] [--ref tasks/T3b_blq/reference/pkanalix_individual.csv]
"""
import argparse, csv, math, os, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_all import auclast_lulog
import score_nca as sn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def profiles(path):
    subj = defaultdict(list)
    for r in csv.DictReader(open(path)):
        if r["EVID"] != "0":
            continue
        try:
            c = float(r["AVAL"])
        except ValueError:
            continue
        subj[f"{r['DRUG']}_{r['USUBJID']}"].append((float(r["ATPTN"]), c, r["BLQ"] == "1"))
    return {k: sorted(v) for k, v in subj.items()}


def apply_rule(pts, rule):
    """zero: BLQ kept as 0 (data as given). prompt: BLQ before Tmax -> 0, after Tmax -> dropped. drop: all BLQ dropped."""
    meas = [(t, c) for t, c, b in pts if not b]
    tmax = max(meas, key=lambda x: x[1])[0] if meas else math.inf   # first time of the maximum (sorted by time)
    out = []
    for t, c, b in pts:
        if not b:
            out.append((t, c))
        elif rule == "zero" or (rule == "prompt" and t < tmax):
            out.append((t, 0.0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "tasks", "T3b_blq", "inputs", "nca_blq.csv"))
    ap.add_argument("--ref", default=os.path.join(ROOT, "tasks", "T3b_blq", "reference", "pkanalix_individual.csv"))
    a = ap.parse_args()
    if not os.path.exists(a.ref):
        sys.exit(f"reference not found: {a.ref} (run tasks/build_tasks.py with the supplement present)")
    ref = sn.load(a.ref)
    prof = profiles(a.data)
    rules = ["zero", "prompt", "drop"]
    n = 0
    match = defaultdict(int)
    ex = []
    for s, pts in prof.items():
        meas = [(t, c) for t, c, b in pts if not b]
        if not meas or (s, "AUClast") not in ref:
            continue
        tmax = max(meas, key=lambda x: x[1])[0]
        if not any(b and t > tmax for t, _, b in pts):
            continue   # rules agree for this subject
        n += 1
        row = {}
        for rule in rules:
            p = apply_rule(pts, rule)
            auc = auclast_lulog([t for t, _ in p], [c for _, c in p])
            ok = sn.rel_err(auc, ref[(s, "AUClast")]) < 0.01
            match[rule] += ok
            row[rule] = ok
        if len(ex) < 5 and row["zero"] != row["prompt"]:
            ex.append((s, row))
    print(f"subjects with BLQ after Tmax (rules differ): {n}")
    for rule in rules:
        print(f"  AUClast within 1% of PKanalix under rule '{rule}': {match[rule]}/{n} ({100 * match[rule] / max(n, 1):.1f}%)")
    for s, row in ex:
        print("  e.g.", s, row)
    best = max(rules, key=lambda r: match[r])
    print(f"\nPKanalix reference is most consistent with rule '{best}'.")
    if best != "prompt":
        print("-> The T3b prompt's BLQ rule does NOT match the reference. Before running T3b: either change the prompt "
              "to the reference's rule, or build an independent reference for the prompt's rule. Log the decision in "
              "logs/deviations.md.")
    else:
        print("-> Reference follows the prompt's rule; T3b can run as built.")


if __name__ == "__main__":
    main()
