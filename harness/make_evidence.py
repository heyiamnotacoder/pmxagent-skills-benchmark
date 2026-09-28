#!/usr/bin/env python3
"""Freeze an auditable evidence bundle for the write-up.

Writes (committed, small):
  results/evidence/MANIFEST.sha256   sha256 of every file under results/raw/ plus ledger/scores/audit
  results/evidence/provenance.json   git commit, Claude Code version, models seen per arm, skill freeze hash,
                                     PMxAgent image digests, run counts (valid / usage-limited) per arm x task
Writes (not committed; for a data deposit such as Zenodo/OSF):
  ~/pmxbench_evidence/pmxbench_evidence_<stamp>.tar.gz  raw transcripts + outputs + ledger + scores + logs,
  and its sha256 in results/evidence/ so the deposited archive can be matched to this repo.
Usage: make_evidence.py
"""
import csv, datetime, hashlib, json, os, subprocess, tarfile
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
EV = os.path.join(RES, "evidence")
OUTDIR = os.path.expanduser("~/pmxbench_evidence")
EXTRA = ["results/runs.csv", "results/runs.csv.bak-20260928", "results/scores.csv", "results/summary.csv",
         "results/summary.md", "results/isolation_audit.csv", "logs/deviations.md", "logs/skill_changes.md",
         "logs/calibration.txt", "env/versions.txt", "skills/FROZEN.sha256"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).stdout.strip()


def main():
    os.makedirs(EV, exist_ok=True); os.makedirs(OUTDIR, exist_ok=True)
    files = sorted(os.path.relpath(os.path.join(dp, f), ROOT)
                   for dp, _, fs in os.walk(os.path.join(RES, "raw")) for f in fs)
    files += [p for p in EXTRA + sorted(os.path.relpath(os.path.join(ROOT, "logs", f), ROOT)
                                        for f in os.listdir(os.path.join(ROOT, "logs")))
              if os.path.exists(os.path.join(ROOT, p)) and p not in files]
    with open(os.path.join(EV, "MANIFEST.sha256"), "w") as m:
        for p in files:
            m.write(f"{sha(os.path.join(ROOT, p))}  {p}\n")
    ledger = list(csv.DictReader(open(os.path.join(RES, "runs.csv"))))
    counts = Counter((r["arm"], r["task"], r["status"]) for r in ledger if r["rep"] != "0")
    prov = {
        "created": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": run(["git", "rev-parse", "HEAD"]),
        "git_dirty": bool(run(["git", "status", "--porcelain", "--untracked-files=no"])),
        "claude_code_versions": sorted({r["claude_version"] for r in ledger}),
        "models_seen_per_arm": {a: sorted({r["model_seen"] for r in ledger if r["arm"] == a and r["model_seen"]})
                                for a in sorted({r["arm"] for r in ledger})},
        "skills_frozen_sha256": sha(os.path.join(ROOT, "skills", "FROZEN.sha256")),
        "pmxagent_images": [l.strip() for l in open(os.path.join(ROOT, "env", "versions.txt")) if "sha256:" in l],
        "run_counts": {f"{a}|{t}|{s}": n for (a, t, s), n in sorted(counts.items())},
        "n_files_in_manifest": len(files),
    }
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    tgz = os.path.join(OUTDIR, f"pmxbench_evidence_{stamp}.tar.gz")
    with tarfile.open(tgz, "w:gz") as t:
        for p in files + ["results/evidence/MANIFEST.sha256"]:
            t.add(os.path.join(ROOT, p), arcname=p)
    prov["archive"] = {"file": os.path.basename(tgz), "sha256": sha(tgz), "bytes": os.path.getsize(tgz)}
    json.dump(prov, open(os.path.join(EV, "provenance.json"), "w"), indent=1)
    print(json.dumps(prov["archive"]), f"\n{len(files)} files in manifest -> {EV}")


if __name__ == "__main__":
    main()
