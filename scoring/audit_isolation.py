#!/usr/bin/env python3
"""Audit every run transcript for attempts to look outside its own workspace -> results/isolation_audit.csv.

Flags, per run: mentions of another run's id or folder, the run archive, parent-directory paths, Claude Code's
own session/memory folders, or this project repo. Only tool calls (what the agent actually did) are checked, not the
system prompt. Stdlib only.  Usage: audit_isolation.py
"""
import csv, glob, json, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw")
PATTERNS = {
    "other_run_id": None,   # filled per run
    "run_area": None,       # run area paths other than the run's own folder (filled per run)
    "parent_dir": re.compile(r"(^|[\s'\"=(])\.\./|cd \.\.(\s|$|;|&)"),
    "claude_state": re.compile(r"\.claude/(projects|todos|memory)|\.claude\.json"),
    "project_repo": re.compile(r"projects/cptpaper|psp470325|pkanalix_individual"),
}
RUN_AREA = re.compile(r"pmxbench_runs/A\d/(runs|base)|pmxbench_runs/?[\"'\s]|pmxbench_runs/_pmxagent|pmxbench_archive")
RUNID = re.compile(r"A\d_T[0-9a-z]+_[a-z_]*?r\d\d_\d{8}-\d{6}")


def tool_inputs(path):
    for line in open(path, errors="replace"):
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") != "assistant":
            continue
        for c in ev.get("message", {}).get("content", []):
            if c.get("type") == "tool_use":
                yield json.dumps(c.get("input"))


def main():
    rows = []
    for tr in sorted(glob.glob(os.path.join(RAW, "*", "*", "*", "transcript.jsonl"))):
        arm, task, runid = tr.split(os.sep)[-4:-1]
        hits = {k: 0 for k in PATTERNS}
        for inp in tool_inputs(tr):
            hits["other_run_id"] += sum(1 for m in RUNID.findall(inp) if m != runid)
            own = inp.replace(f"/runs/{runid}", "/OWN")
            hits["run_area"] += len(RUN_AREA.findall(own))
            for k, rx in PATTERNS.items():
                if rx is not None:
                    hits[k] += len(rx.findall(inp))
        rows.append({"runid": runid, "arm": arm, "task": task, **hits, "flagged": any(hits.values())})
    out = os.path.join(ROOT, "results", "isolation_audit.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    flagged = [r for r in rows if r["flagged"]]
    print(f"{len(rows)} transcripts audited, {len(flagged)} flagged -> {out}")
    for r in flagged:
        print(r)


if __name__ == "__main__":
    main()
