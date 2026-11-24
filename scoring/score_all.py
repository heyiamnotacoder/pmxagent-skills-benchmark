#!/usr/bin/env python3
"""Score every run in results/raw/<arm>/<task>/<runid>/ and write results/scores.csv.

NCA tasks (T1, T3a, T3b, T3c, T3e): paper metric (score_nca.score) vs tasks/<task>/reference/pkanalix_individual.csv.
  The individual-results file is picked by coverage of reference (subject, parameter) keys, never by accuracy.
T2 (case study): completion + internal consistency, recomputed here from the agent's own simulated data with
  independent AUClast code (no skill code). Primary `summary_consistent_pct` = the pre-specified check (commit
  08ea7b3): AUClast recomputed lin-up/log-down. `summary_consistent_any_rule_pct` = post-hoc sensitivity
  (logs/deviations.md §13, §15): the prompt names no AUC rule, so linear or lin-up/log-down both count.
T3d (oral 1-CM): typical Cmax/Tmax/AUCinf vs analytical truth (|RE| < 1% correct).
Stdlib only.  Usage: score_all.py [--arm A3] [--task T1_nca]
"""
import argparse, csv, glob, json, math, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runstore
import score_nca as sn
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness"))
import ledger   # the valid-run rule shared with the harness (results/exclusions.csv)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw")
NCA_TASKS = {"T1_nca", "T3a_messy", "T3b_blq", "T3c_units", "T3e_large"}
PMX_ARMS = {"A1", "A1b"}
PMX_HTTP_ENDPOINT = re.compile(r"(?:localhost|127\.0\.0\.1):5762/(?:NCA|ER|PK|DATA|LIBRARY)\b", re.I)
BASH_READONLY_CMD = re.compile(r"^\s*(?:grep|egrep|fgrep|rg|cat|head|tail|less|sed|awk)\b")
SUBJ_COLS = ["drug_subject", "drug", "subject", "usubjid", "id"]


def read_any(path):
    """(id, parameter, value) rows in file order: long (DRUG, PPTESTCD, PPSTRESN) via score_nca.read_rows, else wide
    (one column per parameter). [] when the file is not a results table."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rd = csv.DictReader(f)
            cols = rd.fieldnames or []
            low = {c.strip().lower(): c for c in cols}
            if "pptestcd" in low and "ppstresn" in low and "drug" in low:
                return sn.read_rows(path)
            pcols = {c: sn.canonical(c) for c in cols if sn.canonical(c)}
            if not pcols:
                return []
            rows = list(rd)
    except (UnicodeDecodeError, csv.Error, KeyError):
        return []
    out = []
    for r in rows:
        if "drug" in low and ("usubjid" in low or "subject" in low or "id" in low):
            sc = low.get("usubjid") or low.get("subject") or low.get("id")
            subj = f"{r[low['drug']].strip()}_{r[sc].strip()}"
            if r[low["drug"]].strip().endswith("_" + r[sc].strip()):
                subj = r[low["drug"]].strip()
        else:
            k = next((low[c] for c in SUBJ_COLS if c in low), None)
            if k is None:
                return []
            subj = r[k].strip()
        for c, p in pcols.items():
            try:
                out.append((subj, p, float(r[c])))
            except (TypeError, ValueError):
                out.append((subj, p, math.nan))
    return out


def load_any(path, order=None):
    """{(subject, parameter): value} from a results file; `order` (score_nca.subject_order of the reference) turns on
    row-order matching of drug-only rows (logs/deviations.md §29)."""
    return sn.to_table(read_any(path), order)[0]


def load_scored(run_dir, scored_file, ref):
    """The table a run was scored on, loaded exactly as scoring loads it; None without the file."""
    p = os.path.join(run_dir, scored_file or "")
    return load_any(p, sn.subject_order(ref)) if scored_file and os.path.exists(p) else None


def pick_individual(run_dir, ref, order=None):
    """(file, coverage, matched_by_row_order) for the CSV that covers most reference (subject, parameter) keys, never
    chosen by accuracy. Coverage counts rows matched by row order (§29; `order` defaults to the reference's); at equal
    coverage a file whose rows carry subject IDs wins, then the first in path order."""
    order = order or sn.subject_order(ref)
    best, best_key, best_matched = None, (0, 0), 0
    cands = sorted(glob.glob(os.path.join(run_dir, "output", "**", "*.csv"), recursive=True))
    cands += sorted(glob.glob(os.path.join(run_dir, "pmxagent_data", "**", "*.csv"), recursive=True))
    refkeys = set(ref)
    for c in cands:
        table, matched = sn.to_table(read_any(c), order)
        key = (len(refkeys.intersection(table)), -matched)
        if key[0] and key > best_key:
            best, best_key, best_matched = c, key, matched
    return best, best_key[0] / len(refkeys) if refkeys else 0, bool(best_matched)


UNSCORABLE = "no scorable individual file"   # scores.csv `note` of a completed NCA run with nothing to score
ROW_ORDER = "subjects matched by row order"   # scores.csv `note` of a run scored on a drug-only file (§29)
DIGITS = 6   # run scores are stored at this precision and rounded only for display (peer review S10; §29)


def score_nca_run(run_dir, task):
    return score_nca_dir(run_dir, sn.load(os.path.join(ROOT, "tasks", task, "reference", "pkanalix_individual.csv")))


def score_nca_dir(run_dir, ref):
    """Score the run's best-covering individual file. With none (nothing maps to a subject, even by row order), score
    an empty table with the same metric: every parameter and `overall` are 0, since a completed run counts whatever
    its score (paper/SPEC.md; logs/deviations.md §17). A run scored by row order (§29) also gets
    `overall_charorder`: the same file matched in character order of subject number (1, 10, 2, ...), for the post hoc
    upper bound in stats.py only."""
    row, by_order = _score_nca(run_dir, ref, sn.subject_order(ref))
    if by_order:
        row["note"] = ROW_ORDER
        row["overall_charorder"] = _score_nca(run_dir, ref, sn.subject_order(ref, character=True))[0]["overall"]
    return row


def _score_nca(run_dir, ref, order):
    """(scores.csv fields, scored by row order?) for one run with drug-only rows matched in `order`."""
    f, cov, by_order = pick_individual(run_dir, ref, order)
    r = sn.score(load_any(f, order) if f else {}, ref)
    row = {"scored_file": os.path.relpath(f, run_dir) if f else "", "coverage_pct": round(100 * cov, 2),
           "overall": round(r["overall"], DIGITS), "npts_match_pct": round(r["terminal_points_match_pct"], DIGITS)}
    row.update({f"{p}_pct": round(r[p]["correct_pct"], DIGITS) for p in sn.PARAMS})
    if not f:
        row["note"] = UNSCORABLE
    return row, by_order


def pmxagent_call_counts(run_dir):
    """Single-pass (mcp_calls, http_calls) from transcript.jsonl, or (None, None) without one.
    mcp_calls counts `mcp__pmxagent__*` tool uses. http_calls counts Bash commands (excluding read-only search/view
    commands) and Write/Edit script payloads targeting PMxAgent's R Plumber API (:5762/{NCA,ER,PK,DATA,LIBRARY})."""
    p = os.path.join(run_dir, "transcript.jsonl")
    if not os.path.exists(p):
        return None, None
    mcp = http = 0
    for c in runstore.tool_uses(p):
        name = str(c.get("name", ""))
        inp = c.get("input") or {}
        if name.startswith("mcp__pmxagent__"):
            mcp += 1
        elif name == "Bash":
            cmd = str(inp.get("command", ""))
            if not BASH_READONLY_CMD.match(cmd) and PMX_HTTP_ENDPOINT.search(cmd):
                http += 1
        elif name in ("Write", "Edit"):
            body = str(inp.get("content", "") if name == "Write" else inp.get("new_string", ""))
            if PMX_HTTP_ENDPOINT.search(body):
                http += 1
    return mcp, http


def pmxagent_tool_calls(run_dir):
    """Number of PMxAgent MCP tool calls (`mcp__pmxagent__*`) in the run's transcript; None without one."""
    return pmxagent_call_counts(run_dir)[0]


def pmxagent_http_calls(run_dir):
    """Number of direct Plumber HTTP endpoint calls (:5762/{NCA,ER,PK,DATA,LIBRARY}); None without a transcript."""
    return pmxagent_call_counts(run_dir)[1]


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


def auclast_linear(t, c):
    """Linear-trapezoidal AUC from first time to last measurable (>0) concentration."""
    pts = sorted((a, b) for a, b in zip(t, c) if not math.isnan(b))
    last = max((i for i, (_, b) in enumerate(pts) if b > 0), default=-1)
    return sum((pts[i + 1][0] - pts[i][0]) * (pts[i][1] + pts[i + 1][1]) / 2 for i in range(last))


AUC_RULES = {"lin-up/log-down": auclast_lulog, "linear": auclast_linear}   # the T2 prompt names no AUC method


def find_col(cols, *pats):
    for p in pats:
        for c in cols:
            if re.fullmatch(p, c.strip(), re.I):
                return c
    return None


# Column-name patterns for an agent's simulated-data CSV, tried in order (first pattern that matches any column wins).
SIM_COLS = {
    "id": ("usubjid", "subjid", "id", "subject", "subj", "subject_id", "sim.?id"),
    "time": ("time", "atptn", "t", "time_?h", "time_?d(ays?)?", "nfrlt", "afrlt"),
    "conc": ("conc", "aval", "cp", "dv", "ipred", "c", "concentration", "cc", "conc_.*"),
    "dose": ("dose", "dosegrp", "dose_?mg", "dose_?group", "dose_level", "grp", "group"),
}


def sim_columns(cols):
    """The id, time, conc and dose columns read_sim would use (None where no pattern matches)."""
    return {k: find_col(cols, *p) for k, p in SIM_COLS.items()}


def read_sim(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return None
    cols = list(rows[0])
    sc = sim_columns(cols)
    idc, tc, cc, dc = sc["id"], sc["time"], sc["conc"], sc["dose"]
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


_MASS_UG = {"mg": 1e3, "ug": 1.0, "ng": 1e-3}
_VOL_ML = {"l": 1e3, "ml": 1.0}
_TIME_H = {"h": 1.0, "hr": 1.0, "day": 24.0, "days": 24.0}


def ec50_h_ug_per_ml(value, units):
    """EC50 converted to h·µg/mL (the unit of PMxAgent's own case-study EC50), or None when `units` is not one
    mass/volume·time AUC unit. Only units are converted; the value is never re-derived (deviations §25).
    Accepted: one mass, one time, one volume, a single `/` with the volume right after it and time not divided
    (mg*h/L, mg/L*h, (mg/L)*h, h*ng/mL, "AUC (ng/mL * h)"); rates such as ng/mL/h or mg/(L*h) are rejected."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    s = re.sub(r"\s+", "*", str(units or "").strip().lower().replace("µ", "u").replace("μ", "u").replace("·", "*"))
    mass = re.findall(r"(?<![a-z])(mg|ug|ng)(?![a-z])", s)
    vol = re.findall(r"/\*?(ml|l)(?![a-z])", s)
    time = re.findall(r"(?<![a-z])(h|hr|days?)(?![a-z])", s)
    if len(mass) != 1 or len(vol) != 1 or len(time) != 1 or s.count("/") != 1:
        return None
    return float(f"{v * _MASS_UG[mass[0]] / _VOL_ML[vol[0]] * _TIME_H[time[0]]:.6g}")


def candidate_csvs(run_dir, declared):
    """CSV files the run produced (output/, and pmxagent_data/ for A1), those named in results.json `files` first.

    Declared paths may be relative, absolute on the run machine, or container paths (/data/<runid>/...), so they are
    matched by their longest path suffix that exists among the run's files."""
    found = [p for sub in ("output", "pmxagent_data")
             for p in sorted(glob.glob(os.path.join(run_dir, sub, "**", "*.csv"), recursive=True))]
    rel = {p: os.path.relpath(p, run_dir).split(os.sep) for p in found}
    vals = list(declared.values()) if isinstance(declared, dict) else list(declared or [])
    first = []
    for d in (v for v in vals if isinstance(v, str) and v.lower().endswith(".csv")):
        parts = [x for x in d.replace("\\", "/").split("/") if x]
        best, best_n = None, 0
        for p, r in rel.items():
            n = 0
            while n < min(len(parts), len(r)) and parts[-1 - n] == r[-1 - n]:
                n += 1
            if n > best_n:
                best, best_n = p, n
        if best and best not in first:
            first.append(best)
    return first + [p for p in found if p not in first]


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
               ec50_h_ug_ml=ec50_h_ug_per_ml(j.get("ec50"), j.get("ec50_units")),
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
    for q in candidate_csvs(run_dir, j.get("files")):
        sim = read_sim(q)
        if sim and len(sim) >= 60:
            out["sim_file"] = os.path.relpath(q, run_dir)
            break
        sim = None
    if sim:
        by = defaultdict(lambda: {"cmax": [], **{m: [] for m in AUC_RULES}})
        for (dose, _), s in sim.items():
            by[dose]["cmax"].append(max(s["c"]))
            for m, rule in AUC_RULES.items():
                by[dose][m].append(rule(s["t"], s["c"]))
        mean = lambda xs: sum(xs) / len(xs)
        n_ok = n_ok_any = n = 0
        matched = []   # per dose: the AUC rules that reproduce the reported mean
        for dose, v in by.items():
            try:
                g = gs[float(dose)]
                rep_auc, rep_cmax = float(g["mean_AUClast"]), float(g["mean_Cmax"])
            except (KeyError, ValueError, TypeError):
                continue
            rules = {m for m in AUC_RULES if sn.rel_err(rep_auc, mean(v[m])) < 0.01}
            matched.append(rules)
            n += 2
            cmax_ok = sn.rel_err(rep_cmax, mean(v["cmax"])) < 0.01
            n_ok += ("lin-up/log-down" in rules) + cmax_ok        # primary: pre-specified rule only
            n_ok_any += bool(rules) + cmax_ok                     # sensitivity: either rule
        common = set.intersection(*matched) if matched else set()
        out["auc_method"] = ("lin-up/log-down" if "lin-up/log-down" in common else common.pop() if common
                             else "mixed" if matched and all(matched) else "none")   # nothing compared: none
        out["n_subjects_sim"] = len(sim)
        out["summary_consistent_pct"] = round(100 * n_ok / n, 1) if n else None
        out["summary_consistent_any_rule_pct"] = round(100 * n_ok_any / n, 1) if n else None
    else:
        out["note"] = "sim file not parseable"
    return out


def score_oral_run(run_dir):
    rj = glob.glob(os.path.join(run_dir, "output", "**", "results.json"), recursive=True)
    if not rj:   # a valid run that left nothing scores 0 of 3, like an unscorable NCA run (§22)
        return {"completed": False, "note": "no results.json", "overall": 0.0}
    try:
        j = json.load(open(rj[0]))
    except ValueError:
        return {"completed": False, "note": "results.json unparseable", "overall": 0.0}
    truth = json.load(open(os.path.join(ROOT, "tasks", "T3d_oral", "reference", "truth.json")))
    out = {"completed": True, "model_used": j.get("model_used")}
    ok = 0
    for k in ("typical_cmax_mg_per_L", "typical_tmax_h", "typical_auc_inf_mg_h_per_L"):
        try:
            re_ = sn.rel_err(float(j[k]), truth[k])
        except (KeyError, TypeError, ValueError):
            re_ = math.inf
        out[k + "_re_pct"] = round(100 * re_, 3) if re_ != math.inf else None
        ok += re_ < 0.01
    out["overall"] = round(100 * ok / 3, DIGITS)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm"); ap.add_argument("--task")
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "scores.csv"))
    a = ap.parse_args()
    runs = {r["runid"]: r for r in csv.DictReader(open(os.path.join(ROOT, "results", "runs.csv")))}
    excluded = ledger.exclusions()
    rows, rescanned = [], set()
    for run_dir in sorted(glob.glob(os.path.join(RAW, "*", "*", "*"))):
        arm, task, runid = run_dir.split(os.sep)[-3:]
        if task.startswith("_") or (a.arm and arm != a.arm) or (a.task and task != a.task):
            continue
        if runid not in runs:   # still running
            continue
        rescanned.add(runid)
        if not ledger.valid(runs[runid], excluded):   # usage-limit / infra-failed / excluded runs are not scored (§22)
            continue
        if task in NCA_TASKS:
            r = score_nca_run(run_dir, task)
        elif task == "T2_case":
            r = score_case_run(run_dir)
        elif task == "T3d_oral":
            r = score_oral_run(run_dir)
        else:
            continue
        mcp_calls, http_calls = pmxagent_call_counts(run_dir) if arm in PMX_ARMS else (None, None)
        rows.append({"runid": runid, "arm": arm, "task": task, "status": runs[runid]["status"], **r,
                     "pmxagent_tool_calls": mcp_calls, "pmxagent_http_calls": http_calls})
    kept = len(runstore.merge_rows(a.out, rows, rescanned)) - len(rows)
    print(f"{len(rows)} runs scored, {kept} rows kept for runs not on this machine -> {a.out}")


if __name__ == "__main__":
    main()
