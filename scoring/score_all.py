#!/usr/bin/env python3
"""Score every run in results/raw/<arm>/<task>/<runid>/ and write results/scores.csv.

NCA tasks (T1, T3a, T3b, T3c, T3e): paper metric (score_nca.score) vs tasks/<task>/reference/pkanalix_individual.csv.
  The individual-results file is picked by coverage of reference (subject, parameter) keys, never by accuracy.
T2 (case study): completion + internal consistency, recomputed here from the agent's own simulated data with an
  independent linear-up/log-down AUClast (no skill code).
T3d (oral 1-CM): typical Cmax/Tmax/AUCinf vs analytical truth (|RE| < 1% correct).
Stdlib only.  Usage: score_all.py [--arm A3] [--task T1_nca]
"""
import argparse, csv, glob, json, math, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_nca as sn

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw")
NCA_TASKS = {"T1_nca", "T3a_messy", "T3b_blq", "T3c_units", "T3e_large"}
SUBJ_COLS = ["drug_subject", "drug", "subject", "usubjid", "id"]


def load_any(path):
    """Long (DRUG, PPTESTCD, PPSTRESN) via score_nca.load, else wide (one column per parameter)."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rd = csv.DictReader(f)
            cols = rd.fieldnames or []
            low = {c.strip().lower(): c for c in cols}
            if "pptestcd" in low and "ppstresn" in low and "drug" in low:
                return sn.load(path)
            pcols = {c: sn.ALIASES[c.strip().lower()] for c in cols if c.strip().lower() in sn.ALIASES}
            if not pcols:
                return {}
            rows = list(rd)
    except (UnicodeDecodeError, csv.Error, KeyError):
        return {}
    out = {}
    for r in rows:
        if "drug" in low and ("usubjid" in low or "subject" in low or "id" in low):
            sc = low.get("usubjid") or low.get("subject") or low.get("id")
            subj = f"{r[low['drug']].strip()}_{r[sc].strip()}"
            if r[low["drug"]].strip().endswith("_" + r[sc].strip()):
                subj = r[low["drug"]].strip()
        else:
            k = next((low[c] for c in SUBJ_COLS if c in low), None)
            if k is None:
                return {}
            subj = r[k].strip()
        for c, p in pcols.items():
            try:
                out[(subj, p)] = float(r[c])
            except (TypeError, ValueError):
                out[(subj, p)] = math.nan
    return out


def pick_individual(run_dir, ref):
    best, best_cov = None, 0
    cands = glob.glob(os.path.join(run_dir, "output", "**", "*.csv"), recursive=True)
    cands += glob.glob(os.path.join(run_dir, "pmxagent_data", "**", "*.csv"), recursive=True)
    refkeys = set(ref)
    for c in cands:
        d = load_any(c)
        cov = len(refkeys.intersection(d))
        if cov > best_cov:
            best, best_cov = c, cov
    return best, best_cov / len(refkeys) if refkeys else 0


def score_nca_run(run_dir, task):
    ref = sn.load(os.path.join(ROOT, "tasks", task, "reference", "pkanalix_individual.csv"))
    f, cov = pick_individual(run_dir, ref)
    if not f:
        return {"scored_file": "", "coverage_pct": 0.0, "overall": 0.0, "note": "no scorable individual file"}
    r = sn.score(load_any(f), ref)
    row = {"scored_file": os.path.relpath(f, run_dir), "coverage_pct": round(100 * cov, 2), "overall": round(r["overall"], 2),
           "npts_match_pct": round(r["terminal_points_match_pct"], 2)}
    row.update({f"{p}_pct": round(r[p]["correct_pct"], 2) for p in sn.PARAMS})
    return row


def auclast_lulog(t, c):
    """Linear-up/log-down AUC from first time to last measurable (>0) concentration."""
    pts = sorted((a, b) for a, b in zip(t, c) if not math.isnan(b))
    last = max((i for i, (_, b) in enumerate(pts) if b > 0), default=-1)
    auc = 0.0
    for i in range(last):
        (t0, c0), (t1, c1) = pts[i], pts[i + 1]
        dt = t1 - t0
        if c1 < c0 and c1 > 0 and c0 > 0:
            auc += (c0 - c1) * dt / math.log(c0 / c1)
        else:
            auc += (c0 + c1) * dt / 2
    return auc


def find_col(cols, *pats):
    for p in pats:
        for c in cols:
            if re.fullmatch(p, c.strip(), re.I):
                return c
    return None


def read_sim(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    cols = list(rows[0])
    idc = find_col(cols, "usubjid", "id", "subject", "subj", "subject_id", "sim.?id")
    tc = find_col(cols, "time", "atptn", "t", "time_?h", "time_?d(ays?)?", "nfrlt", "afrlt")
    cc = find_col(cols, "conc", "aval", "cp", "dv", "ipred", "c", "concentration", "cc", "conc_.*")
    dc = find_col(cols, "dose", "dosegrp", "dose_?mg", "dose_?group", "dose_level", "grp", "group")
    ev = find_col(cols, "evid")
    if not (idc and tc and cc and dc):
        return None
    subj = defaultdict(lambda: {"t": [], "c": [], "dose": None})
    for r in rows:
        if ev and r.get(ev, "0").strip() not in ("0", "0.0", ""):
            continue
        try:
            t, c = float(r[tc]), float(r[cc])
        except ValueError:
            continue
        dose = re.sub(r"[^0-9.]", "", r[dc]) or None
        key = (dose, r[idc])
        subj[key]["t"].append(t); subj[key]["c"].append(c); subj[key]["dose"] = dose
    return subj


def score_case_run(run_dir):
    out = {"note": ""}
    rj = glob.glob(os.path.join(run_dir, "output", "**", "results.json"), recursive=True)
    if not rj:
        out["note"] = "no results.json"; out["completed"] = False
        return out
    try:
        j = json.load(open(rj[0]))
    except ValueError:
        out["note"] = "results.json unparseable"; out["completed"] = False
        return out
    gs = {float(re.sub(r"[^0-9.]", "", str(g.get("dose_mg")))): g for g in j.get("group_summary", [])}
    out.update(completed=sorted(gs) == [10.0, 30.0, 100.0], ec50=j.get("ec50"), ec50_units=j.get("ec50_units"),
               seed=j.get("seed"), n_timepoints=j.get("n_timepoints_per_subject"),
               pk_parameters=json.dumps(j.get("pk_parameters"), separators=(",", ":")))
    try:
        auc = {d: float(g["mean_AUClast"]) for d, g in gs.items()}
        out["auc_ratio_100_10"] = round(auc[100.0] / auc[10.0], 3)
        e = float(j["ec50"])
        out["ec50_between_group_aucs"] = min(auc.values()) <= e <= max(auc.values())
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        pass
    # recompute group means from the agent's own simulated data
    sim = None
    files = j.get("files") or {}
    paths = list(files.values()) if isinstance(files, dict) else list(files)
    for p in [x for x in paths if isinstance(x, str)] + glob.glob(os.path.join(run_dir, "output", "**", "*.csv"), recursive=True):
        q = p if os.path.isabs(p) and os.path.exists(p) else os.path.join(run_dir, p if not p.startswith("output/") else p)
        if not os.path.exists(q):
            q = os.path.join(run_dir, "output", os.path.basename(p))
        if os.path.exists(q) and q.endswith(".csv"):
            sim = read_sim(q)
            if sim and len(sim) >= 60:
                out["sim_file"] = os.path.relpath(q, run_dir)
                break
            sim = None
    if sim:
        by = defaultdict(lambda: {"auc": [], "cmax": []})
        for (dose, _), s in sim.items():
            by[dose]["auc"].append(auclast_lulog(s["t"], s["c"])); by[dose]["cmax"].append(max(s["c"]))
        n_ok = n = 0
        for dose, v in by.items():
            try:
                g = gs[float(dose)]
            except (KeyError, ValueError, TypeError):
                continue
            for k, rk in (("auc", "mean_AUClast"), ("cmax", "mean_Cmax")):
                mine = sum(v[k]) / len(v[k])
                n += 1
                n_ok += sn.rel_err(float(g[rk]), mine) < 0.01
        out["n_subjects_sim"] = len(sim)
        out["summary_consistent_pct"] = round(100 * n_ok / n, 1) if n else None
    else:
        out["note"] = "sim file not parseable"
    return out


def score_oral_run(run_dir):
    truth = json.load(open(os.path.join(ROOT, "tasks", "T3d_oral", "reference", "truth.json")))
    rj = glob.glob(os.path.join(run_dir, "output", "**", "results.json"), recursive=True)
    if not rj:
        return {"completed": False, "note": "no results.json"}
    try:
        j = json.load(open(rj[0]))
    except ValueError:
        return {"completed": False, "note": "results.json unparseable"}
    out = {"completed": True, "model_used": j.get("model_used")}
    ok = 0
    for k in ("typical_cmax_mg_per_L", "typical_tmax_h", "typical_auc_inf_mg_h_per_L"):
        try:
            re_ = sn.rel_err(float(j[k]), truth[k])
        except (KeyError, TypeError, ValueError):
            re_ = math.inf
        out[k + "_re_pct"] = round(100 * re_, 3) if re_ != math.inf else None
        ok += re_ < 0.01
    out["overall"] = round(100 * ok / 3, 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm"); ap.add_argument("--task")
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "scores.csv"))
    a = ap.parse_args()
    ledger = {r["runid"]: r for r in csv.DictReader(open(os.path.join(ROOT, "results", "runs.csv")))}
    rows = []
    for run_dir in sorted(glob.glob(os.path.join(RAW, "*", "*", "*"))):
        arm, task, runid = run_dir.split(os.sep)[-3:]
        if task.startswith("_") or (a.arm and arm != a.arm) or (a.task and task != a.task):
            continue
        if runid not in ledger:   # still running
            continue
        if ledger[runid]["status"] != "ok" or ledger[runid]["is_error"] == "True":   # usage-limit / crashed runs
            continue
        if task in NCA_TASKS:
            r = score_nca_run(run_dir, task)
        elif task == "T2_case":
            r = score_case_run(run_dir)
        elif task == "T3d_oral":
            r = score_oral_run(run_dir)
        else:
            continue
        rows.append({"runid": runid, "arm": arm, "task": task, "status": ledger[runid]["status"], **r})
    cols = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} runs scored -> {a.out}")


if __name__ == "__main__":
    main()
