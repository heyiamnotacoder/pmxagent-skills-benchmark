#!/usr/bin/env python3
"""Freeze an auditable evidence bundle for the write-up.

Writes (committed, small):
  results/evidence/MANIFEST.sha256   sha256 of every file under results/raw/ plus ledger/scores/audit
  results/evidence/provenance.json   git commit; per task, the Claude Code pin and the versions of its scored runs
                                     (one pinned version per task, deviations §15); models seen per arm (scored runs);
                                     skill freeze hash; PMxAgent image digests and its pinned CLAUDE.md hash (A1b);
                                     ledger status counts and valid-run counts per arm x task
Writes (not committed; for a data deposit such as Zenodo/OSF):
  ~/pmxbench_evidence/pmxbench_evidence_<stamp>.tar.gz  raw transcripts + outputs + ledger + scores + logs,
  and its sha256 in results/evidence/ so the deposited archive can be matched to this repo.
Usage: make_evidence.py
"""
import csv, datetime, hashlib, json, os, re, subprocess, sys, tarfile
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger, run_arm   # noqa: E402  (the one valid-run rule; the pinned PMxAgent CLAUDE.md hash)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
EV = os.path.join(RES, "evidence")
VERSIONS = os.path.join(ROOT, "env", "versions.txt")
OUTDIR = os.path.expanduser("~/pmxbench_evidence")
# Besides results/raw/ and logs/: every file directly under results/ (ledger, exclusions, scores, summaries, stats,
# audits, checks, reports) and the pins.
EXTRA = ["env/versions.txt", "skills/FROZEN.sha256"]
PIN = re.compile(r"^claude-code-pin (\S+): (\S+)")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def read_pins(path=VERSIONS):
    """{task or "default": Claude Code version} from the `claude-code-pin` lines of env/versions.txt."""
    with open(path) as f:
        return {m[1]: m[2] for m in map(PIN.match, f) if m}


def scored(rows, excluded):
    """Ledger rows that are scored: benchmark reps (not preflights) that are valid runs (ledger.valid)."""
    return [r for r in rows if r["rep"] != "0" and ledger.valid(r, excluded)]


def claude_code_by_task(rows, excluded, pins):
    """Per task: its pin, the Claude Code versions of its scored runs, and whether they are one version = the pin."""
    runs, out = scored(rows, excluded), {}
    for t in sorted({r["task"] for r in runs}):
        vs = sorted({r["claude_version"] for r in runs if r["task"] == t})
        pin = pins.get(t, pins.get("default"))
        out[t] = {"pin": pin, "scored_versions": vs, "n_scored": sum(r["task"] == t for r in runs),
                  "single_version_on_pin": vs == [pin]}
    return out


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT).stdout.strip()


def main():
    # Before anything is written: this script rewrites tracked files (the manifest), which would read as dirty.
    commit, dirty = run(["git", "rev-parse", "HEAD"]), bool(run(["git", "status", "--porcelain", "--untracked-files=no"]))
    os.makedirs(EV, exist_ok=True); os.makedirs(OUTDIR, exist_ok=True)
    files = sorted(os.path.relpath(os.path.join(dp, f), ROOT)
                   for dp, _, fs in os.walk(os.path.join(RES, "raw")) for f in fs)
    top = sorted(f"results/{f}" for f in os.listdir(RES) if os.path.isfile(os.path.join(RES, f)))
    logs = sorted(f"logs/{f}" for f in os.listdir(os.path.join(ROOT, "logs")))
    files += [p for p in top + EXTRA + logs if os.path.exists(os.path.join(ROOT, p)) and p not in files]
    with open(os.path.join(EV, "MANIFEST.sha256"), "w") as m:
        for p in files:
            m.write(f"{sha(os.path.join(ROOT, p))}  {p}\n")
    rows = list(csv.DictReader(open(ledger.LEDGER, newline="")))
    excluded = ledger.exclusions()
    counts = Counter((r["arm"], r["task"], r["status"]) for r in rows if r["rep"] != "0")
    valid = Counter((r["arm"], r["task"]) for r in scored(rows, excluded))
    by_task = claude_code_by_task(rows, excluded, read_pins())
    prov = {
        "created": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "git_commit": commit,
        "git_dirty": dirty,
        "claude_code_versions_all_ledger_rows": sorted({r["claude_version"] for r in rows}),
        "claude_code_by_task": by_task,
        "models_seen_per_arm": {a: sorted({r["model_seen"] for r in scored(rows, excluded)
                                           if r["arm"] == a and r["model_seen"]})
                                for a in sorted({r["arm"] for r in scored(rows, excluded)})},
        "skills_frozen_sha256": sha(os.path.join(ROOT, "skills", "FROZEN.sha256")),
        "pmxagent_images": [l.strip() for l in open(VERSIONS) if "sha256:" in l],
        "pmxagent_claude_md_sha256": run_arm.PMX_CLAUDE_MD_SHA256,
        "run_counts": {f"{a}|{t}|{s}": n for (a, t, s), n in sorted(counts.items())},
        "valid_run_counts": {f"{a}|{t}": n for (a, t), n in sorted(valid.items())},
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
    for t, v in by_task.items():
        print(f"{t}: {v['n_scored']} scored runs on Claude Code {', '.join(v['scored_versions'])} (pin {v['pin']})"
              + ("" if v["single_version_on_pin"] else "  <- DRIFT: log it (issue #3) before depositing"))


if __name__ == "__main__":
    main()
