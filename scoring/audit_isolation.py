#!/usr/bin/env python3
"""Audit every run transcript for attempts to look outside its own workspace -> results/isolation_audit.csv.

Flags, per run: mentions of another run's id or folder, the run archive, parent-directory paths, Claude Code's
session/memory folders outside the rep's own HOME, or this project repo. For an A1 run whose raw folder holds
pmx_root.json (the harness emptied PMxAgent's shared /data/ and /figures/ before the agent started, deviations §20),
those shared folders count as the run's own: reading them is how it fetches its tools' outputs. Only tool calls (what the agent actually did) are checked, not the
system prompt. Stdlib only.  Usage: audit_isolation.py
"""
import csv, glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runstore
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "harness"))
import ledger, pmx_root

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw")
PATTERNS = {
    "other_run_id": None,   # filled per run
    "run_area": None,       # run area paths other than the run's own folder (filled per run)
    "parent_dir": re.compile(r"(^|[\s'\"=(])\.\./|cd \.\.(\s|$|;|&)"),
    "claude_state": re.compile(r"\.claude/(projects|todos|memory)|\.claude\.json"),
    "project_repo": re.compile(r"projects/(cptpaper|pmxagent)\b|psp470325|pkanalix_individual"),
}
RUN_AREA = re.compile(r"pmxbench_runs/A\d[a-z]?/(runs|base)|pmxbench_runs/?[\"'\s]|pmxbench_runs/_pmxagent|pmxbench_archive")
RUNID = re.compile(r"A\d[a-z]?_T[0-9a-z]+_[a-z_]*?r\d\d_\d{8}-\d{6}")


def tool_inputs(path):
    for c in runstore.tool_uses(path):
        yield json.dumps(c.get("input"))


def audit_run(transcript, runid):
    """{pattern: number of hits} over the tool calls in one run's transcript (its raw folder = the file's folder)."""
    hits = {k: 0 for k in PATTERNS}
    clean_root = pmx_root.started_clean(os.path.dirname(transcript))
    for inp in tool_inputs(transcript):
        hits["other_run_id"] += sum(1 for m in RUNID.findall(inp) if m != runid)
        own = (inp.replace(f"/runs/{runid}.home/.claude", "/OWNHOME")   # the rep's own Claude Code state
               .replace(f"/runs/{runid}", "/OWN").replace(f"_pmxagent/data/{runid}", "OWN"))   # A1 data folder
        if clean_root:
            own = own.replace("pmxbench_runs/_pmxagent/data", "OWN").replace("pmxbench_runs/_pmxagent/figures", "OWN")
        hits["run_area"] += len(RUN_AREA.findall(own))
        for k, rx in PATTERNS.items():
            if rx is not None:
                hits[k] += len(rx.findall(own))
    return hits


def main():
    excluded = ledger.exclusions()
    rows = []   # runs whose transcripts are not on this machine keep their committed rows
    for tr in sorted(glob.glob(os.path.join(RAW, "*", "*", "*", "transcript.jsonl"))):
        arm, task, runid = tr.split(os.sep)[-4:-1]
        hits = audit_run(tr, runid)
        rows.append({"runid": runid, "arm": arm, "task": task, **hits, "flagged": any(hits.values()),
                     "excluded": runid in excluded})
    out = os.path.join(ROOT, "results", "isolation_audit.csv")
    allrows = runstore.merge_rows(out, rows, {r["runid"] for r in rows})
    valid_flagged = [r for r in rows if r["flagged"] and not r["excluded"]]
    excl_flagged = [r for r in rows if r["flagged"] and r["excluded"]]
    print(f"{len(rows)} transcripts audited here, {len(valid_flagged)} valid flagged "
          f"({len(excl_flagged)} excluded flagged); {len(allrows)} rows in {out}")
    for r in valid_flagged:
        print("VALID FLAGGED:", r)


if __name__ == "__main__":
    main()
