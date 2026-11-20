"""Where a run's artefacts live, and how derived per-run tables are updated.

Raw run folders (results/raw/<arm>/<task>/<runid>/) are git-ignored and deposited on Zenodo per task bundle, so this
machine may hold only some of them. Derived tables (scores, isolation audit) are therefore updated by run ID: rows for
runs that were re-scanned here are replaced; rows for runs whose raw folder is absent are kept as committed.
Stdlib only.
"""
import csv, glob, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "results", "raw")
EVIDENCE = os.path.join(ROOT, "results", "evidence")


def manifests():
    """Every committed evidence manifest (T1 at the top level, later bundles in sub-folders)."""
    return sorted(glob.glob(os.path.join(EVIDENCE, "**", "MANIFEST.sha256"), recursive=True))


def merge_rows(path, new_rows, rescanned, key="runid"):
    """Write `path` = existing rows not in `rescanned` (order kept) + `new_rows`. Columns = union, first-seen order."""
    old = list(csv.DictReader(open(path, newline=""))) if os.path.exists(path) else []
    rows = [r for r in old if r[key] not in rescanned] + list(new_rows)
    cols = []
    for r in rows:
        cols += [k for k in r if k not in cols]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols or [key])
        w.writeheader(); w.writerows(rows)
    return rows


def output_hashes(arm, task, runid, raw=RAW, manifests=None):
    """{path relative to output/: sha256} from the local raw folder, else from the evidence manifests; {} if neither."""
    p = os.path.join(raw, arm, task, runid, "output_sha256.json")
    if os.path.exists(p):
        return json.load(open(p))
    prefix = f"results/raw/{arm}/{task}/{runid}/output/"
    out = {}
    for m in (manifests if manifests is not None else globals()["manifests"]()):
        for line in open(m):
            h, _, rel = line.rstrip("\n").partition("  ")
            if rel.startswith(prefix):
                out[os.path.join(*rel[len(prefix):].split("/"))] = h
    return out


def tool_uses(transcript):
    """Yield every tool_use block ({"name", "input", ...}) the agent made, from a Claude Code stream-json transcript.
    Unparseable lines are skipped."""
    for line in open(transcript, encoding="utf-8", errors="replace"):
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") != "assistant":
            continue
        for c in (ev.get("message") or {}).get("content") or []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                yield c
